# RAID System - NLCI Portal

An internal management dashboard built for the RAID Department at NLCI. This Flask-based application integrates library management, attendance tracking, internal communication, and administrative tools into a single unified interface.

## 📋 Features

### 🔐 Authentication & Security

* **OTP-based Login:** Secure email login restricted to `@nlife.in` domain and whitelisted external users.
* **Role-Based Access Control (RBAC):** Distinct permissions for `user`, `tester`, and `admin` roles.
* **Profile Management:** View current status, role, and activity history.

### 📚 Modules

1. **Library Catalog (`/library`)**
* Fetches real-time book data from Google Sheets.
* Genre filtering (Books, Reports, Journals).
* One-click book reservation requests.


2. **Attendance System (`/attendance`)**
* Daily Check-in/Check-out logging.
* **Leave Management:** Apply for Casual (CL), Sick (SL), or Annual (AL) leaves.
* **Balance Tracker:** Visual progress bars showing remaining leave quotas.


3. **Team Chat (`/chat`)**
* Real-time internal messaging system.
* Support for Direct Messages (DMs) and Group Channels.
* Message history persistence via JSON.


4. **Internal Blog (`/blog`)**
* News and announcements feed.
* Admin-exclusive WYSIWYG-style posting interface.


5. **Database View (`/database_view`)**
* Pandas-powered data visualization.
* Searchable and sortable table views of institutional records fetched from external CSVs.



### 🛠 Administrative Tools

* **Dashboard:** Centralized view for Admins to manage the system.
* **Request Handling:** Approve/Reject book requests and leave applications.
* **User Management:** detailed user list with the ability to promote/demote user roles.

### 🎨 UI/UX

* **Modern Design:** Built with **Tailwind CSS** and **Lucide Icons**.
* **Global Dark Mode:** Automatic theme switching based on system preference or user toggle.
* **Responsive:** Fully mobile-friendly layout.

---

## 🏗 Tech Stack

* **Backend:** Python 3, Flask
* **Data Processing:** Pandas
* **Database:** * Local JSON storage (`database.json`, `chat.json`, `blog_posts.json`) for lightweight persistence.
* Google Sheets (via CSV export) for read-only data (Library/Records).


* **Frontend:** HTML5, Jinja2 Templates, Tailwind CSS (CDN), JavaScript.

---

## 🚀 Installation & Setup

### Prerequisites

* Python 3.8+
* Pip

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/raid-system.git
cd raid-system

```

### 2. Install Dependencies

Create a `requirements.txt` or install manually:

```bash
pip install flask pandas requests

```

### 3. Configuration

The system currently uses hardcoded credentials in `auth.py` and `library.py`. For production, **it is highly recommended** to replace these with environment variables.

* **SMTP Settings:** Update `auth.py` with your email sender credentials.
* **Google Sheets:** Update the CSV URLs in `library.py` and `database_view.py`.

### 4. Run the Application

```bash
python app.py

```

The application will start at `http://127.0.0.1:5000/`.

---

## 📂 Project Structure

```text
raid-system/
├── app.py                # Application entry point & Blueprint registration
├── auth.py               # Login, Logout, and Profile logic
├── database.py           # JSON database helper functions
├── admins.py             # Admin dashboard logic
├── library.py            # Library module (Google Sheets integration)
├── attendance.py         # Attendance & Leave logic
├── chat.py               # Chat system logic
├── blog.py               # Blog/News logic
├── database_view.py      # Data viewer logic
├── ideas.txt             # Future roadmap & AI features
├── templates/            # HTML Templates
│   ├── index.html        # Main Dashboard
│   ├── auth.html         # Login Page
│   ├── library.html      # Library Catalog
│   ├── attendance.html   # Attendance Portal
│   ├── chat.html         # Chat Interface
│   ├── blog.html         # News Feed
│   ├── admins.html       # Admin Console
│   ├── profile.html      # User Profile
│   └── database_view.html# Data Tables
└── README.md             # Project Documentation

```

---

## 🔮 Roadmap (AI Integration)

Based on internal planning (`ideas.txt`), the following AI-powered features are planned for future releases:

* **"Talk to Your Data":** Natural language querying for the Database View using Gemma 3 12B.
* **Sentiment Watchdog:** Automated conflict detection in public chat channels.
* **The Archivist:** Auto-generated promotional blog posts for under-read library books.
* **Smart Moderation:** Pre-publish AI filtering for blog posts and chat bans.
* **Automated Changelogs:** AI summarization of weekly system activity.

---

## 🛡 License

Internal Software - New Life Computer Institution (NLCI).
Unauthorized copying or distribution is strictly prohibited.
