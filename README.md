# Slaydchi_bot
I buiilt a telegram bot for students to get ready presentations and referats , independent work papers in just minutes with AI. This bot gets topic and some kind of required informations to generate context from the users and makes a word and pptx files.


# 🤖 SlaydchiBot – AI-Powered Telegram Assistant

SlaydchiBot is an AI-powered Telegram bot that helps students automatically generate academic content such as theses, reports, Word documents, and more. It also includes a built-in payment system, referral system, balance management, and admin tools.

---

## ✨ Features

### 📄 Content Generation

* ✍️ Thesis generation (multi-language)
* 📝 Word document creation from text and images
* 📊 Presentation generation (coming soon)
* 📚 Academic report generation (referat support)
* 📑 Mustaqil ish generation support

### 🌍 Multi-Language Support

* Uzbek 🇺🇿
* Russian 🇷🇺
* English 🇬🇧

Language can be selected at startup.

---

### 💰 Balance & Payment System

* User balance tracking
* Manual payment confirmation via admin
* Receipt upload (image or PDF)
* Automatic balance updates
* Payment verification system
* Pricing system per content type

---

### 👥 Referral System

* Each user gets a personal referral link
* Users earn bonus balance for inviting friends
* Automatic referral tracking
* Referral reward system

---

### 🧠 AI Integration

Supports multiple AI models via API key management.

Features:

* Multiple API keys support
* Model rotation support
* Admin model management
* Failover system ready

---

### 👑 Admin Features

Admins can:

* Add API keys
* Add AI models
* Send messages to users
* Confirm or reject payments
* View statistics
* Manage system usage

---

### 📊 Statistics System

* Tracks user usage
* Tracks payments
* Tracks income
* Tracks generation count

---

## 🏗️ Project Structure

```
project/
│
├── bot.py
├── db.json
├── .env
│
├── services/
│   ├── models.py
│   ├── balance.py
│   ├── limits.py
│   ├── statistics.py
│   ├── access_control.py
│
├── text/
│   └── translations.py
│
├── text2word/
│   └── text2word.py
│
├── mustaqil/
│   └── mustaqil_ish.py
│
├── tezis.py
├── referat_2gpt.py
│
└── README.md
```

---

## ⚙️ Requirements

* Python 3.10+
* Telegram Bot Token
* OpenAI or compatible API (optional)
* SQLite database

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/slaydchibot.git
cd slaydchibot
```

---

### 2. Create virtual environment

```bash
python -m venv venv
```

Activate:

Windows:

```bash
venv\Scripts\activate
```

Linux / Mac:

```bash
source venv/bin/activate
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If requirements.txt does not exist, install manually:

```bash
pip install aiogram python-dotenv openpyxl python-docx
```

---

### 4. Create `.env` file

```
BOT_TOKEN=your_telegram_bot_token
```

---

### 5. Run the bot

```bash
python bot.py
```

---

## 🗄️ Database

The project uses SQLite database.

Databases include:

* users
* balance
* api_keys
* models
* statistics
* limits

Database initializes automatically.

---

## 🔐 Environment Variables

| Variable  | Description        |
| --------- | ------------------ |
| BOT_TOKEN | Telegram bot token |

---

## 🧑‍💻 Admin Configuration

Edit in code:

```python
ADMINS = [YOUR_TELEGRAM_USER_ID]
```

---

## 💳 Payment Flow

1. User selects payment amount
2. User uploads receipt
3. Admin confirms or rejects
4. Balance updated automatically

---

## 🔄 Referral Flow

Referral link format:

```
https://t.me/your_bot?start=ref_USERID
```

Reward is automatically added.

---

## 🧠 How AI Generation Works

1. User selects content type
2. Bot checks balance and limits
3. Bot uses available AI model
4. File generated and sent to user
5. Balance deducted

---

## 🛡️ Security Features

* Rate limiting
* Admin access control
* Payment verification
* Balance protection
* API key management

---

## 🚀 Future Improvements

* Presentation generation
* Automatic payments
* Web dashboard
* User analytics panel
* Subscription plans

---

## 📸 Example Commands

Start bot:

```
/start
```

Create Word file:

```
📝 Create Word File
```

Check balance:

```
💰 Balance
```

---

## 🧩 Technologies Used

* Python
* Aiogram 3
* SQLite
* Telegram Bot API
* OpenAI API (optional)
* python-docx
* openpyxl

---

## 🤝 Contributing

Pull requests are welcome.

For major changes, open an issue first.

---

## 📄 License

MIT License

---

## 👨‍💻 Author

Developed by SlaydchiBot Team

---

## ⭐ Support

If you like this project, please give it a star on GitHub ⭐

---
