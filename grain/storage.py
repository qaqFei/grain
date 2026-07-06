import pathlib
import subprocess
import zipfile
import io
import typing
import json

import zstandard

import grain.package
import grain.utils
import grain.githubapi
import grain.local
from grain.logger import Logger

class Git:
    def __init__(self, git: str, cwd: pathlib.Path):
        self.git = git
        self.cwd = cwd
    
    def _create(self, args: list[str]):
        Logger.info("Running git command:", *map(lambda x: x if " " not in x else f'"{x}"', args))
        return subprocess.run([self.git, *args], cwd=self.cwd, capture_output=True)
    
    def run(self, args: list[str]):
        pro = self._create(args)
        if pro.returncode != 0:
            raise Exception(f"Git failed: {pro.stderr.decode('utf-8')}")
        return self
    
    def run_get(self, args: list[str]):
        pro = self._create(args)
        return pro.stdout.decode("utf-8").strip() if pro.returncode == 0 else None
    
    def get_first_commit(self):
        return self.run_get(["rev-list", "--max-parents=0", "HEAD"])
    
    def reset_soft_to_first_commit(self):
        commhash = self.get_first_commit()
        if commhash is not None:
            self.run(["reset", "--soft", commhash])
        return self
    
    def set_remote(self, remote: str):
        try: self.run(["remote", "set-url", "origin", remote])
        except Exception: self.run(["remote", "add", "origin", remote])
    
    def commit(self, message: str):
        if self.run_get(["status", "--porcelain"]):
            self.run(["commit", "-m", message])
        return self

def init_repo(repo: pathlib.Path, git: str):
    if repo.exists():
        raise Exception("Repo already exists")
    
    repo.mkdir()
    Git(git, repo).run(["init"]).run(["branch", "-M", "main"])
    
    (repo / "packages").mkdir()
    (repo / ".grain.initialized-flag").touch()

def check_initialized(repo: pathlib.Path):
    if not (repo / ".grain.initialized-flag").exists():
        raise Exception("Repo not initialized")

def set_remote(repo: pathlib.Path, git: str, remote: str):
    check_initialized(repo)
    Git(git, repo).set_remote(remote)

def push_repo(repo: pathlib.Path, git: str, message: str, merge_all: bool = False):
    g = Git(git, repo)
    if merge_all: g.reset_soft_to_first_commit()
    g.run(["add", "-A"]).commit(message).run(["push", "-u", "origin", "main", "-f"])

def pack_package_name(name: str, version: int):
    return f"{name}=={version}.grain"

def pack_package_as_bytes(path: pathlib.Path, info: grain.package.UnionPackageInfo):
    buf = io.BytesIO()
    zip = zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED)
    
    zip.writestr("info.json", json.dumps(info.dump(), **grain.utils.jdump_args()))
    
    if (path / "README.md").is_file():
        zip.write(path / "README.md", "README.md")
    
    source_name = grain.package.get_source_filename(info)
    zip.write(path / source_name, source_name)
    
    grain.utils.walk_dir(path / "files", lambda p: zip.write(p, p.relative_to(path)))

    zip.close()
    buf.seek(0)
    return buf.read()

def draft_release(repo: pathlib.Path, git: str, data_dir: pathlib.Path, package_path: pathlib.Path, version: typing.Optional[int] = None):
    info = grain.package.load_package_info(package_path)
    name = grain.package.get_name_from_info(info)
    
    if not grain.package.check_package_name(name):
        raise Exception("Invalid package name")
    
    extname_coll = set()
    for externals in info.requirements.externals.get_all():
        for i in externals:
            extname, extver = grain.utils.parse_package_name(i)
            if extname in extname_coll: raise Exception("External name repeated")
            extname_coll.add(extname)
            
            if not check_release_exist(repo, extname, extver):
                raise Exception(f"External {i} not found")
    
    if version is None:
        version = 0
        
        while True:
            if not (repo / "packages" / pack_package_name(name, version)).exists():
                Logger.info("Found useable version:", version)
                break
            
            version += 1
            
    filename = pack_package_name(name, version)
    grain.local.remove_package(data_dir, name, version)
    
    Logger.info("Packing package:", filename)
    
    store_packed = pack_package_as_bytes(package_path, info)
    final = zstandard.ZstdCompressor().compress(store_packed)
    
    (repo / "packages" / filename).write_bytes(final)
    push_repo(repo, git, f"Drafted {name} {version}")

def check_release_exist(repo: pathlib.Path, name: str, version: int):
    return (repo / "packages" / pack_package_name(name, version)).exists()

def get_release_zstd(repo: pathlib.Path, name: str, version: int):
    filename = pack_package_name(name, version)
    if not (repo / "packages" / filename).exists():
        raise Exception("Package not found")

    return (repo / "packages" / filename).read_bytes()

def get_all_packages(repo: pathlib.Path|str):
    if isinstance(repo, pathlib.Path):
        for file in (repo / "packages").iterdir():
            if not file.is_file(): continue
            yield grain.utils.parse_package_name(file.name[:-len(".grain")])
    else:
        for file in grain.githubapi.get_item_desc(repo, "/packages"):
            if file["type"] != "file": continue
            yield grain.utils.parse_package_name(file["name"][:-len(".grain")])

def get_latest_package_version(repo: pathlib.Path|str, name: str):
    return max((v for n, v in get_all_packages(repo) if n == name), default=0)
