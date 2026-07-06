import pathlib
import dataclasses
import typing
import json
import shutil
import os

import grain.utils

def get_config_path():
    return str(pathlib.Path.home() / ".grain")

@dataclasses.dataclass
class Config:
    data_dir: typing.Optional[str] = None
    git: typing.Optional[str] = None
    compiler_gpp: typing.Optional[str] = None
    storage_repo_dir: typing.Optional[str] = None
    online_storage_repo_url: typing.Optional[str] = None
    
    def load(self, path: str):
        config_data: dict = {}
        
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception as e:
                return e
        
        self.data_dir = config_data.get("data_dir")
        self.git = config_data.get("git")
        self.compiler_gpp = config_data.get("compiler_gpp")
        self.storage_repo_dir = config_data.get("storage_repo_dir")
        self.online_storage_repo_url = config_data.get("online_storage_repo_url")
        self.use_ghproxy = config_data.get("use_ghproxy", False)
        self.save(path)
    
    def save(self, path: str):
        config_data = {
            "data_dir": self.data_dir,
            "git": self.git,
            "compiler_gpp": self.compiler_gpp,
            "storage_repo_dir": self.storage_repo_dir,
            "online_storage_repo_url": self.online_storage_repo_url,
            "use_ghproxy": self.use_ghproxy
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, **grain.utils.jdump_args())
        except Exception as e:
            return e
    
    @staticmethod
    def from_default():
        config = Config()
        config.load(get_config_path())
        return config
    
    def auto_data_dir(self):
        if not self.data_dir:
            self.data_dir = str(pathlib.Path.home() / ".grain_data")
    
    def auto_compiler(self):
        if not self.compiler_gpp:
            self.compiler_gpp = shutil.which("g++")
    
    def auto_git(self):
        if not self.git:
            self.git = shutil.which("git")
    
    def auto_online_storage_repo_url(self):
        if not self.online_storage_repo_url:
            self.online_storage_repo_url = "https://github.com/qaqFei/grain_storage.git"
    
    def storage_repo_as_path(self):
        return pathlib.Path(self.storage_repo_dir)
    
    def data_dir_as_path(self):
        return pathlib.Path(self.data_dir)
    
    def ensure_default_build_path(self):
        path = self.data_dir_as_path() / "build"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def check_git(self):
        if not self.git:
            raise Exception("Git is not configured")
        return self
    
    def get_storage(self):
        return self.storage_repo_as_path() if self.storage_repo_dir else self.online_storage_repo_url
