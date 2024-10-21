import os
import time
import aiohttp
import asyncio
import aiofiles

API_KEY = 'mrp_QpoboUm9xRGrH26mHVFg30BJRgtF4iCNnn7Y54rBGFmimRiHS8oDrpuKeMAo'
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'User-Agent': 'Modrinth Mod Downloader'
}

BASE_URL = "https://api.modrinth.com/v2"
MODS_DIR = "mods"  # Папка для сохранения модов
RATE_LIMIT_SECONDS = 1.2  # Пауза между запросами для предотвращения лимита
LINKS_FILE = "download_links.txt"  # Файл для сохранения ссылок на моды
PAGE_FILE = "last_page.txt"  # Файл для сохранения номера последней страницы

EXCLUDED_TAGS = ['optimization']  # Теги модов, которые нужно исключить

BATCH_SIZE = 1000  # Сохранять ссылки каждые 1000 модов
CONCURRENT_DOWNLOADS = 5  # Максимальное количество одновременных загрузок

async def get_last_page():
    # Получаем номер последней обработанной страницы, если файл существует
    if os.path.exists(PAGE_FILE):
        with open(PAGE_FILE, 'r') as f:
            return int(f.read().strip())
    return 0

async def save_last_page(page):
    # Сохраняем номер последней обработанной страницы
    with open(PAGE_FILE, 'w') as f:
        f.write(str(page))

async def get_all_mods(session):
    print("Запрашиваю список всех модов...")
    url = f"{BASE_URL}/search"
    params = {
        "limit": 100,  # Максимум 100 модов за один запрос
    }
    
    mods = []
    page = await get_last_page()
    params["offset"] = page * 100  # Пропускаем страницы до последней обработанной

    while True:
        print(f"Запрос страницы {page + 1} с модами...")
        async with session.get(url, headers=HEADERS, params=params) as response:
            if response.status != 200:
                print(f"Ошибка при запросе модов: {response.status}")
                break
            data = await response.json()
            hits = data.get("hits", [])
            if not hits:
                print("Больше модов не найдено.")
                break
            mods.extend(hits)
            print(f"Получено {len(hits)} модов. Всего найдено: {len(mods)} модов.")
            params["offset"] = len(mods)  # Сдвиг для следующей страницы
            page += 1

            # Сохраняем страницу и ссылки каждые BATCH_SIZE модов
            if len(mods) >= BATCH_SIZE:
                print(f"Сохранение ссылок и обновление страницы каждые {BATCH_SIZE} модов...")
                await filter_and_save_mods(mods, session)
                await save_last_page(page)
                mods.clear()  # Очищаем список для следующей партии

            # Уважение к лимиту запросов
            await asyncio.sleep(RATE_LIMIT_SECONDS)

    # Сохраняем остаток модов, если их меньше чем BATCH_SIZE
    if mods:
        await filter_and_save_mods(mods, session)
        await save_last_page(page)

async def filter_mods(mods):
    print(f"Фильтрация модов по тегам: исключаем {EXCLUDED_TAGS}...")
    filtered_mods = []
    for mod in mods:
        tags = mod.get("categories", [])
        if not any(tag in EXCLUDED_TAGS for tag in tags):
            filtered_mods.append(mod)
        else:
            print(f"Мод {mod['title']} исключен из-за тегов: {tags}")
    print(f"После фильтрации осталось {len(filtered_mods)} модов.")
    return filtered_mods

async def save_download_link(file_url, status="ещё нет"):
    async with aiofiles.open(LINKS_FILE, 'a') as f:
        await f.write(f"{file_url} - {status}\n")

async def filter_and_save_mods(mods, session):
    filtered_mods = await filter_mods(mods)
    
    tasks = []
    for idx, mod in enumerate(filtered_mods, start=1):
        print(f"\n[{idx}/{len(filtered_mods)}] Поиск ссылки для мода: {mod['title']}...")
        tasks.append(asyncio.create_task(download_latest_version(mod, session)))
    
    await asyncio.gather(*tasks)

async def download_latest_version(mod, session):
    project_id = mod["project_id"]
    project_slug = mod["slug"]
    
    print(f"Запрос версий для мода {mod['title']} (slug: {project_slug})...")
    url = f"{BASE_URL}/project/{project_id}/version"
    async with session.get(url, headers=HEADERS) as response:
        if response.status != 200:
            print(f"Ошибка при получении версии мода {project_slug}: {response.status}")
            return
        versions = await response.json()
    
    if not versions:
        print(f"Нет версий для мода {project_slug}")
        return
    
    # Находим последнюю версию
    latest_version = max(versions, key=lambda v: v["date_published"])
    version_files = latest_version.get("files", [])
    
    if not version_files:
        print(f"Нет файлов для последней версии мода {project_slug}")
        return
    
    # Сохраняем ссылку на первый файл (предполагается, что это основной файл мода)
    file_url = version_files[0]["url"]
    print(f"Найдена ссылка: {file_url}")
    await save_download_link(file_url)

async def download_files():
    if not os.path.exists(LINKS_FILE):
        print(f"Файл {LINKS_FILE} не найден. Сначала выполните поиск ссылок.")
        return
    
    async with aiofiles.open(LINKS_FILE, 'r') as f:
        links = await f.readlines()
    
    tasks = []
    for idx, line in enumerate(links, start=1):
        file_url, status = line.strip().split(' - ')
        if status == "скачен":
            print(f"[{idx}/{len(links)}] Файл уже скачан, пропускаем.")
            continue
        
        print(f"[{idx}/{len(links)}] Скачивание файла: {file_url}...")
        tasks.append(asyncio.create_task(download_file(file_url)))
    
    await asyncio.gather(*tasks)

async def download_file(file_url):
    filename = file_url.split('/')[-1]
    
    # Проверяем, существует ли папка для модов
    if not os.path.exists(MODS_DIR):
        os.makedirs(MODS_DIR)

    # Загружаем файл
    file_path = os.path.join(MODS_DIR, filename)
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as response:
            with open(file_path, 'wb') as file:
                file.write(await response.read())
    
    print(f"Файл {filename} успешно скачан.")

def update_download_status(file_url):
    # Обновляем статус скачанного файла в download_links.txt
    with open(LINKS_FILE, 'r') as f:
        lines = f.readlines()

    with open(LINKS_FILE, 'w') as f:
        for line in lines:
            if file_url in line:
                f.write(f"{file_url} - скачен\n")
            else:
                f.write(line)

async def main():
    print("Выберите действие:")
    print("1 - Поиск ссылок на файлы модов")
    print("2 - Скачивание файлов по сохранённым ссылкам")
    
    choice = input("Ваш выбор (1/2): ")
    
    async with aiohttp.ClientSession() as session:
        if choice == '1':
            await get_all_mods(session)
        elif choice == '2':
            await download_files()
        else:
            print("Неверный выбор. Повторите попытку.")

if __name__ == "__main__":
    asyncio.run(main())
