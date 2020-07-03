# azmeta-pipeline-cli

This is a companion tool for manually loading data in [azmeta-pipeline](https://github.com/wpbrown/azmeta-pipeline).

See [Manual Data Loading](https://github.com/wpbrown/azmeta-pipeline#manual-data-loading) for more details.

## Installation in Azure Cloud Shell

Download the binary and mark the download executable.

```shell
demo@Azure:~$ wget -O azmpcli https://github.com/wpbrown/azmeta-pipeline-cli/releases/latest/download/azmpcli.pyz
demo@Azure:~$ chmod +x azmpcli
```

Run it directly.

```
demo@Azure:~$ ./azmpcli
```

## Installation on Linux, Mac, or WSL

Prerequisites:
* Python 3.6 or newer
* Azure CLI 

Make sure you are logged in to the CLI.

```
demo@machine:~$ az login
```

Download the binary.

```shell
demo@machine:~$ wget -O azmpcli https://github.com/wpbrown/azmeta-pipeline-cli/releases/latest/download/azmpcli.pyz
```

Run with Python.

```
demo@machine:~$ python3 ./azmpcli
```
