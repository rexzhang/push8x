# Push8x

> [!IMPORTANT]
> **Project Status: Early Development** > This project is in its early stages and is undergoing active development. Expect frequent and significant breaking changes as we evolve. We welcome early adopters and contributors!

An push notification exchange server implementation for selfhosted; support from:webhook/smtpd to:webhook/smtp/apprise, custom rules.

`Push8x` mean PushEx/PushExchanger

## Receiver

### receiver.webhook

- not finish yet.

### receiver.smtpd

- receive message via SMTP protocol
- support text/html format
- support authentication and TLS based on nginx

## Sender

### sender.blackhole

- message will be discarded directly
- for debug

### sender.webhook

- not finish yet.

### sender.smtp

- send message via SMTP protocol with other SMTPd service

### sender.apprise

- send message via [AppRise lib](https://github.com/caronc/apprise)

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

## Message Parameter Mapping

eMail example:

    Sender Man <sender.m@example.com>
    Receiver Man <receiver.m@example.com>

    Subject: Test Subject
    Content: Test Content

| Push8X       | eMail(smtpd/smtp)           | apprise                 |
| ------------ | --------------------------- | ----------------------- |
| `from_name`  | eg:`Sender Man`             | n/a                     |
| `from_value` | eg:`sender.m@example.com`   | n/a                     |
| `to_name`    | eg:`Receiver Man`           | n/a                     |
| `to_value`   | eg:`receiver.m@example.com` | eg:`pover://user@token` |
| `title`      | eg:`Test Subject`           | `title`                 |
| `content`    | eg:`Test Content`           | `body`                  |
