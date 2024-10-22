import aiohttp
import asyncio
import json
import os
from typing import List, Dict, Set, Literal
import time
from datetime import datetime
import sys
import re

# Расширенные конфигурационные параметры
CONFIG = {
    "API_BASE_URL": "https://api.modrinth.com/v2",
    "REQUESTS_PER_MINUTE": 290,
    "TIMEOUT_SECONDS": 30,
    "BATCH_SIZE": 50,
    "DELAY_BETWEEN_REQUESTS": 60 / 290,
    "MAX_NAME_LENGTH": 50,
    
    # Настройки для модов
    "MODS_CONFIG": {
        "BLACKLISTED_TAGS": {"optimization", "library"},
        "PROGRESS_FILE": "mods_progress.json",
        "OUTPUT_FILE": "mod_links.json"
    },
    
    # Настройки для текстурпаков
    "TEXTURES_CONFIG": {
        "MIN_MC_VERSION": "1.16",
        "MAX_RESOLUTION": 32,
        "PROGRESS_FILE": "textures_progress.json",
        "OUTPUT_FILE": "texture_links.json"
    }
}

class ModrinthAPI:
    def __init__(self, content_type: Literal["mods", "textures"]):
        self.session = None
        self.processed_pages: Set[int] = set()
        self.content_type = content_type
        self.config = CONFIG["MODS_CONFIG"] if content_type == "mods" else CONFIG["TEXTURES_CONFIG"]
        self.load_progress()
        self.spinner_chars = ['|', '/', '-', '\\']
        self.spinner_idx = 0
        self.current_page = 0

    def load_progress(self) -> None:
        try:
            with open(self.config["PROGRESS_FILE"], 'r') as f:
                self.processed_pages = set(json.load(f))
        except FileNotFoundError:
            self.processed_pages = set()

    def save_progress(self) -> None:
        with open(self.config["PROGRESS_FILE"], 'w') as f:
            json.dump(list(self.processed_pages), f)

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def update_page_spinner(self) -> None:
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
        sys.stdout.write(f'\rОбработка страницы {self.current_page}... {self.spinner_chars[self.spinner_idx]}')
        sys.stdout.flush()

    def format_line(self, name: str, status: str) -> str:
        padded_name = f"- {name} -"
        return f"{padded_name:<{CONFIG['MAX_NAME_LENGTH']}} {status}"

    def extract_resolution(self, description: str) -> int:
        """Извлечение разрешения текстурпака из описания"""
        patterns = [
            r'(\d+)x\s*(?:resolution|текстуры|ресурспак)',
            r'(\d+)\s*x\s*\d+',
            r'(\d+)x'
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, description, re.IGNORECASE):
                return int(match.group(1))
        return 0

    def check_minecraft_version(self, versions: List[str]) -> bool:
        """Проверка версии Minecraft"""
        return any(version >= self.config["MIN_MC_VERSION"] for version in versions)

    async def get_content_list(self, page: int) -> List[Dict]:
        url = f"{CONFIG['API_BASE_URL']}/search"
        params = {
            "offset": page * CONFIG['BATCH_SIZE'],
            "limit": CONFIG['BATCH_SIZE']
        }
        
        # Добавляем специфичные параметры для текстурпаков
        if self.content_type == "textures":
            params["facets"] = '["project_type:resourcepack"]'  # Исправленный формат
        else:
            params["facets"] = '["project_type:mod"]'  # Добавлен фильтр для модов
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('hits', [])
            else:
                raise Exception(f"API error: {response.status}")

    async def get_version_details(self, project_id: str) -> Dict:
        url = f"{CONFIG['API_BASE_URL']}/project/{project_id}/version"
        
        async with self.session.get(url) as response:
            if response.status == 200:
                versions = await response.json()
                if versions:
                    return versions[0]
            return None

    async def process_mod(self, mod: Dict) -> Dict:
        """Обработка мода"""
        mod_name = mod['title']

        if any(tag in self.config['BLACKLISTED_TAGS'] for tag in mod.get('categories', [])):
            print(self.format_line(mod_name, "Пропущен (теги) ❌"))
            return None

        version = await self.get_version_details(mod['project_id'])
        if not version:
            print(self.format_line(mod_name, "Ошибка версии ❌"))
            return None

        print(self.format_line(mod_name, "Успешно ✅"))
        return {
            'name': mod_name,
            'version': version['version_number'],
            'download_url': version['files'][0]['url'] if version['files'] else None,
            'icon_url': mod.get('icon_url', None)
        }

    async def process_texture(self, texture: Dict) -> Dict:
        """Обработка текстурпака"""
        texture_name = texture['title']
        
        # Проверка версии Minecraft
        if not self.check_minecraft_version(texture.get('versions', [])):
            print(self.format_line(texture_name, "Пропущен (версия) ❌"))
            return None
            
        # Проверка разрешения
        resolution = self.extract_resolution(texture.get('description', ''))
        if resolution > self.config["MAX_RESOLUTION"]:
            print(self.format_line(texture_name, f"Пропущен ({resolution}x) ❌"))
            return None

        version = await self.get_version_details(texture['project_id'])
        if not version:
            print(self.format_line(texture_name, "Ошибка версии ❌"))
            return None

        print(self.format_line(texture_name, f"Успешно ({resolution}x) ✅"))
        return {
            'name': texture_name,
            'version': version['version_number'],
            'resolution': resolution,
            'minecraft_versions': texture.get('versions', []),
            'download_url': version['files'][0]['url'] if version['files'] else None,
            'icon_url': texture.get('icon_url', None)
        }

    async def process_page(self, page: int) -> List[Dict]:
        self.current_page = page
        if page in self.processed_pages:
            return []

        items = await self.get_content_list(page)
        results = []

        print(f"\nОбработка страницы {page}:")

        for item in items:
            await asyncio.sleep(CONFIG['DELAY_BETWEEN_REQUESTS'])
            if self.content_type == "mods":
                result = await self.process_mod(item)
            else:
                result = await self.process_texture(item)
            
            if result:
                results.append(result)

        self.processed_pages.add(page)
        self.save_progress()
        return results

    def save_results(self, results: List[Dict]) -> None:
        try:
            with open(self.config['OUTPUT_FILE'], 'r') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = []

        existing_data.extend(results)

        with open(self.config['OUTPUT_FILE'], 'w') as f:
            json.dump(existing_data, f, indent=2)

    async def run(self, max_pages: int = 10):
        try:
            await self.init_session()
            print(f"Начало обработки {'модов' if self.content_type == 'mods' else 'текстурпаков'}...")

            for page in range(max_pages):
                if page in self.processed_pages:
                    print(f"Страница {page} уже обработана, пропускаем...")
                    continue

                results = await self.process_page(page)
                self.save_results(results)

        except Exception as e:
            print(f"Ошибка: {e}")
        finally:
            await self.close_session()

async def main():
    # Запуск сбора модов
    print("=== Сбор модов ===")
    mods_api = ModrinthAPI("mods")
    await mods_api.run()
    
    # Запуск сбора текстурпаков
    print("\n=== Сбор текстурпаков ===")
    textures_api = ModrinthAPI("textures")
    await textures_api.run()

if __name__ == "__main__":
    asyncio.run(main())