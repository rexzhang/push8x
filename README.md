# Push8x

> [!IMPORTANT]
> **Project Status: Early Development** > This project is in its early stages and is undergoing active development. Expect frequent and significant breaking changes as we evolve. We welcome early adopters and contributors!

An push notification exchange server implementation for selfhosted; support from:webhook/smtpd to:webhook/smtp/apprise, custom rules.

`Push8x` mean PushEx/PushExchanger

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
