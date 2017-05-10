import json


class user_setting:
    config_file_path = ".\\config\\config"

    def __init__(self):
        pass

    def get_config(self, category, key):
        if not self.config_file_path:
            return None
        with open(self.config_file_path, 'r') as f:
            config_json = json.load(f)
            if category in config_json:
                return config_json[category].get(key, None)
        return False
