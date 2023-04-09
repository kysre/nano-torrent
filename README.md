# nano-torrent

A simple implementation of torrent network.

## Project start-up

First activate virtualenv.

```shell
source venv/bin/activate
```

### Initialize tracker

This project has a single tracker which should be initialized before peers.

```shell
python init_tracker.py <host>:<port>
```

### Initialize peer

Initialize in share mode:

```shell
python init_client.py share <filename> <tracker_address> <listen_address>
```

Initialize in get mode:

```shell
python init_client.py get <filename> <tracker_address> <listen_address>
```

Every peer which is started in get mode, goes into share mode after downloading
the file.
