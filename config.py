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
