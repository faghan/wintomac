# OVERVIEW

Cronbeat is a simple script to collect statistics from tasks run via cron and to send (emit) those to Microsoft teams using a webhook. Resource intensive tasks can be grouped using shared locks, to prevent failures due to resource limitations.

## Usage

Run task named `task-name` defined in the specified JSON file:

``` bash
$ cronbeat.py run /path/to/tasks.json task-name
```

List previously tasks since last `emit` command:

``` bash
$ cronbeat.py list
```

Send summary of tasks run since last `emit` to Microsoft Teams:

``` bash
$ cronbeat.py emit
```

## Configuration

Configuration options may be saved in `~/.cronbeat.ini`. Simply remove leading dashes from command-line options:

``` toml
log-file = /path/to/log.txt
log-level = INFO
cache = /path/to/cache
webhook = https://url/to/webhook
```

Alternatively, a configuration file may be specified using the `--config` option.


## Tasks

See `example.json` for a simple task library.

``` json
{
    "name-of-task": {
        "commands": [
            ["command1", "arg1", "arg2", ...],
            ["command2"],
            ...
        ],
        "pid": "name-of-pid"
    },
    ...
}
```

The `pid` key is optional and can be used to ensure that only one instance of a task is run at a time (if the value is unique) or that only one instance among different types of task is run at a time (if shared between multiple tasks).

The `commands` list may contain one or more commands. Cronbeat will execute these in order, but will abort if any task returns a non-zero error code or otherwise fails.
