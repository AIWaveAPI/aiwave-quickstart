# Use your own AIWave key in WorkBuddy (Windows)

This local tool adds AIWave entries to WorkBuddy's user-level `models.json`.
It does not change your WorkBuddy account, AIWave billing settings, or other
providers. The installer is source code in this repository; read it before
running it. It uses Python's standard library only.

## Before you start

1. Create **your own** key in the [AIWave Console](https://aiwave.live/console).
   Check its account group and balance. Model requests and WorkBuddy's
   connection test may incur usage charges.
2. Install Python 3.10 or newer and close WorkBuddy. The tool refuses to write
   while a WorkBuddy process is running.
3. Clone or download this repository from GitHub. Run the script locally;
   do not paste your key into a shell command, issue, screenshot, or chat.

```powershell
python scripts/workbuddy_connect.py doctor
python scripts/workbuddy_connect.py list
python scripts/workbuddy_connect.py plan
python scripts/workbuddy_connect.py install
python scripts/workbuddy_connect.py verify
```

`plan` writes nothing and reveals no existing key or configuration values.
`install` repeats the plan, asks you to type `INSTALL`, then prompts for your
key without echoing it. It creates a private backup of the existing file,
adds the selected models, and saves a local record of exactly which entries it
owns. Repeating the install with the same key leaves the file unchanged.
If you already configured one of the same AIWave models manually, the tool
keeps that entry and its existing key untouched, and adds only missing models.

The default selection is a small text-model starter set. For a **batch** of
other models, first inspect `list`, then pass exact IDs together:

```powershell
python scripts/workbuddy_connect.py plan --models deepseek-v4.1-flash,deepseek-v4-pro
python scripts/workbuddy_connect.py install --models deepseek-v4.1-flash,deepseek-v4-pro
```

The live [`/api/pricing`](https://aiwave.live/api/pricing) endpoint determines
current price estimates, default-group eligibility, and the OpenAI endpoint
label. A catalog entry does **not** prove it has a working route, a Chat
Completions adapter, or WorkBuddy tool support. The tool excludes known
non-chat types and leaves tool, image, and reasoning flags off. Context limits
and reasoning levels are not guessed. A model may still be unavailable for
your specific key. If you need another account group, use WorkBuddy's model
settings and verify entitlement separately; this script targets `default`.

After install, open **WorkBuddy > Settings > Models** and run its connection
test. Then select the model in a new conversation and try a small real task.
Saving the JSON, `verify`, and a successful connection test each prove
different things; none proves every WorkBuddy workflow works. Compare the
request's usage and charge in your AIWave Console. See current prices at
[aiwave.live/pricing](https://aiwave.live/pricing).

## Undo and privacy

Close WorkBuddy, then run:

```powershell
python scripts/workbuddy_connect.py undo
```

Undo removes only entries recorded as created by this tool. It keeps other
providers and later user additions. If you changed one of the tool-owned
entries yourself, undo stops and asks for manual review rather than erasing
your edit. Backups are never deleted automatically.

WorkBuddy stores the API key in its local config file. The installer also
creates a private backup that may contain your existing keys. Keep both local;
never upload them. On Windows, the tool removes inherited access from newly
written config, state, and backup files and grants access to the current
account. The script does not print keys, place them in arguments, send them to
AIWave itself, or include them in its state file. WorkBuddy sends your key to
AIWave when you choose to make a request.

If `doctor` reports an unfamiliar schema or install refuses a collision,
use WorkBuddy's model settings UI. Do not edit a damaged JSON file through
this tool. Report a bug without attaching `models.json`, backups, prompts,
responses, or API keys.

WorkBuddy configuration and API behavior: [official model configuration
guide](https://www.workbuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model-Configuration).
