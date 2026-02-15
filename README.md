# push8x

push8x is PushEX/PushExchanger

## Check Config File

```sh
python -m push8x -c dev.toml configcheck
```

## Test Your Config File's Rules

```sh
python -m push8x -c dev.toml ruletest --help

python -m push8x -c dev.toml ruletest
python -m push8x -c dev.toml ruletest --t-value abc@abc.com
```

## Start Push8x Server

```sh
python -m push8x -c dev.toml serve
```
