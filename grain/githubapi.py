import urllib3
import os
from urllib.parse import urlparse

import tqdm

import grain.storage
from grain.logger import Logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USE_GHPROXY = False

def parse_repo_as_owner_and_repo(repo: str):
    repo = repo.strip()
    
    if repo.startswith("git@"):
        after_colon = repo.split(":", 1)[1]
        if after_colon.endswith(".git"):
            after_colon = after_colon[:-4]
        parts = after_colon.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Cannot parse repo: {repo}")
    
    if repo.startswith("http://") or repo.startswith("https://"):
        parsed = urlparse(repo)
        path = parsed.path
        if path.startswith("/"):
            path = path[1:]
        if path.endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Cannot parse repo: {repo}")
    
    if "/" in repo:
        if repo.endswith(".git"):
            repo = repo[:-4]
        parts = repo.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    
    raise ValueError(f"Cannot parse repo: {repo}")

def get_item_desc(repo: str, path: str):
    import requests

    Logger.info(f"looking item desc in {repo}: {path}")
    
    owner, repo = parse_repo_as_owner_and_repo(repo)
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, verify=False)
    
    if response.status_code != 200:
        raise Exception(f"Failed to list files in directory: {response.status_code} {response.text}")

    return response.json()

def get_file(repo: str, path: str):
    import requests
    
    desc = get_item_desc(repo, path)
    
    if not isinstance(desc, dict):
        raise Exception(f"Failed to get file: {path}")
    
    if os.environ.get("USE_GHPROXY", None) is not None or USE_GHPROXY:
        desc["download_url"] = "https://ghproxy.net/" + desc["download_url"]
        
    Logger.info(f"downloading file {desc['download_url']}")
    response = requests.get(desc["download_url"], verify=False, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get("content-length", 0))
    
    data = bytearray()
    for i in tqdm.tqdm(response.iter_content(chunk_size=1024), desc=f"downloading {path}", total=total_size // 1024, unit="KB"):
        data.extend(i)
    
    return data

def get_release_zstd(repo: str, name: str, version: int):
    filename = grain.storage.pack_package_name(name, version)
    return get_file(repo, f"/packages/{filename}")
