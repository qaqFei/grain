import pathlib
import zipfile
import io
import typing
import shutil

import grain.storage
import grain.package
import grain.utils
from grain.logger import Logger

def pack_package_name(name: str, version: int):
    return f"{name}=={version}"

def ensure_package(repo: pathlib.Path, data_dir: pathlib.Path, name: str, version: int, _visited: typing.Optional[set[tuple[str, int]]] = None):
    if _visited is None: _visited = set()
    _visited.add((name, version))
    
    dirname = data_dir / "packages" / pack_package_name(name, version)
    
    if not dirname.exists():
        zipdata = grain.storage.get_release_zip(repo, name, version)
        zip = zipfile.ZipFile(io.BytesIO(zipdata))
        zip.extractall(dirname)

        info = grain.package.load_package_info(dirname)
        
        if isinstance(info, grain.package.LibraryInfo):
            includes_dir = dirname / ".grain" / "includes" / info.namespace
            libs_dir = dirname / ".grain" / "libs"
            
            includes_dir.mkdir(parents=True)
            libs_dir.mkdir(parents=True)
            
            for dir in info.exports.includes.get():
                dir = grain.package.get_path_relative_to_package(dirname, dir)
                shutil.copytree(dir, includes_dir, dirs_exist_ok=True)

            for file in info.exports.libs.get():
                file = grain.package.get_path_relative_to_package(dirname, file)
                shutil.copy2(file, libs_dir)
            
            raw_files = dirname / "files"
            if raw_files.exists():
                shutil.rmtree(dirname / "files")
        
        (dirname / ".grain" / "version").write_text(str(version))
    else: info = grain.package.load_package_info(dirname)
    
    externals = info.requirements.externals.get()
    
    for sub in map(grain.utils.parse_package_name, externals):
        if sub in _visited: continue
        ensure_package(repo, data_dir, *sub, _visited=_visited)

    Logger.info(f"Ensured package: {name} {version}")
    return dirname

def get_version(pkg_dir: pathlib.Path):
    path = pkg_dir / ".grain" / "version"
    return int(path.read_text())

def clean_packages(data_dir: pathlib.Path):
    shutil.rmtree(data_dir / "packages")
