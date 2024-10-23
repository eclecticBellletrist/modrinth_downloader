import asyncio
from api.labirinth import ModrinthAPI

async def main():
    # Запуск сбора модов
    print("=== Сбор модов ===")
    mods_api = ModrinthAPI("mods")
    await mods_api.run()

    # Запуск сбора текстурпаков
    print("\n=== Сбор текстурпаков ===")
    textures_api = ModrinthAPI("textures")
    await textures_api.run()

if __name__ == "__links_parse_main__":
    asyncio.run(main())
