# Grain

A C++ package manager.

Default storage repo: `https://github.com/qaqFei/grain_storage`, its code repo: `https://github.com/qaqFei/grain_libraries`

## Install

```bash
pip install git+https://github.com/qaqFei/grain.git
grain info # init config
```

## Usage

```bash
grain info # show the info and config, if not exist, init config

grain config set <key> <value> # set a kv pair in config, like this:
grain config set use_ghproxy True
grain config set storage_repo_dir D:/grain_storage

grain package new <lib/app> <name> # create a new package, like this:
grain package new lib mylib
grain package new app myapp

grain package find <name> # find a package, like this:
grain package find mylib
grain package find myl

grain package add-external <name> # add a external package, like this:
grain package add-external gnumeric

grain package build [dir] [...args] # build the package, like this:
grain package build
grain package build ./myapp
grain package build . --run --release --out ./prog --macro MY_MACRO=1

grain package draft-release [dir] # draft a release, like this:
grain package draft-release
grain package draft-release ./mylib
grain package draft-release . --force-version 0

grain package clean # clean the local packages

grain package add-test [dir] # add a test package to a library package, like this:
grain package add-test
grain package add-test ./mylib

grain package run-test [dir] [...args] # run the test package, like this:
grain package run-test
grain package run-test --release

grain storage init # init the storage repo
grain storage set-remote <url> # set the remote storage repo url
grain storage push # push the storage repo manually
```
