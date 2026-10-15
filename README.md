# Bayyen --- Construction Project Management System

**Bayyen** is a Django-based construction project management web
application designed to make project progress, item status, task
completion, and coordination between project stakeholders easier to
track.
Bayyen brings project management and live site monitoring together through Fazza, our on-site robot interface.

The project is being developed for an **Expo 2030 Riyadh challenge**
concept. It includes role-based workspaces for project managers,
consultant engineers, and contractor engineers, plus a link to
**Fazza**, the live site robot interface.

> **Project status:** Prototype / development build. Review the
> configuration and security notes before deploying or sharing a
> production instance.

------------------------------------------------------------------------

## Overview

Construction work involves multiple teams, deadlines, task updates, and
review handovers. Bayyen brings key item information and workflow status
into one place so stakeholders can see what needs attention and follow
up with the relevant team.

### Key capabilities

-   **Role-based sign-in** using email and password.
-   **Project Manager dashboard** with overall progress, item counts,
    statuses, contractor companies, zones, and deadlines.
-   **Consultant Engineer dashboard** with project progress and an item
    list for review and follow-up.
-   **Contractor Engineer dashboard** showing items assigned to the
    signed-in contractor.
-   **Item details** with item information, task information, and
    relevant comments.
-   **Task status workflow** including Pending, In Progress, Pending
    Review, Completed, and Needs Correction.
-   **Item review statuses** including Not Started, In Progress, Pending
    Review, Needs Revision, and Completed.
-   **Comments and file attachment fields** for stakeholder
    communication.
-   **Fazza entry point** from the Consultant dashboard to open the live
    site robot interface on the local network.

## User roles

  -----------------------------------------------------------------------
  Role                                Workspace
  ----------------------------------- -----------------------------------
  Project Manager                     Project-wide item overview and item
                                      details; communication with the
                                      responsible consultant.

  Consultant Engineer                 Project item dashboard, item review
                                      and follow-up, and communication
                                      related to items and tasks.

  Contractor Engineer                 Dashboard limited to items assigned
                                      to that contractor, item details,
                                      task status updates, and submission
                                      for review.

  Site Engineer                       User role used for task assignment
                                      in the data model. A dedicated Site
                                      Engineer dashboard is not currently
                                      listed in the main application
                                      routes.
  -----------------------------------------------------------------------

Access and actions are controlled by the Django views. The available
actions can vary by role and item state.

## Technology stack

-   **Python**
-   **Django** --- web framework
-   **SQLite** --- development database
-   **Django Templates** --- server-rendered HTML
-   **HTML and CSS** --- user interface
-   **Git and GitHub** --- source control

## Repository structure

``` text
bayyin_project/
├── manage.py
├── bayyin_project/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── core/
    ├── migrations/
    ├── static/
    │   └── core/
    │       ├── css/
    │       └── images/
    ├── templates/
    │   └── core/
    ├── forms.py
    ├── models.py
    ├── urls.py
    ├── views.py
    └── tests.py
```

## Run locally

### Prerequisites

-   Python installed on your computer.
-   Git, if you are cloning the repository.
-   A terminal such as PowerShell on Windows.

### 1. Clone the repository

``` bash
git clone https://github.com/TaifAlosaimi/Bayyen-expo2030.git
cd Bayyen-expo2030
```

> If the repository URL or repository name changes, use the current
> clone URL shown on GitHub.

### 2. Create and activate a virtual environment

**Windows PowerShell**

``` powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the activation method approved for
your machine or run the commands from Command Prompt:

``` bat
.venv\Scripts\activate.bat
```

### 3. Install Django

The current development environment uses Django 6.1.2. Install the
matching version to reproduce that environment:

``` bash
python -m pip install "Django==6.1.2"
```

If a `requirements.txt` file is added to the repository later, prefer
installing dependencies from that file:

``` bash
python -m pip install -r requirements.txt
```

### 4. Apply database migrations

``` bash
python manage.py migrate
```

### 5. Create an administrator account (optional)

``` bash
python manage.py createsuperuser
```

### 6. Start the development server

``` bash
python manage.py runserver
```

Open the local development URL:

-   Application: `http://127.0.0.1:8000/`
-   Sign in: `http://127.0.0.1:8000/login/`
-   Django admin: `http://127.0.0.1:8000/admin/`

The database starts with the records you create locally. A fresh clone
should not be expected to contain the demonstration accounts or sample
items from another computer.

## Fazza --- Live Site Robot

The Consultant dashboard includes a **Fazza --- Live Site Robot** button
that opens:

``` text
http://192.168.4.1/
```

This is a local-network address for the Fazza robot interface, not a
public website. It will only work when the device running the browser
can reach the robot on the required network. The address may need to be
configured for a different network or demonstration setup.

## Data model

The main Django models are:

-   **User** --- Django user account with a project role and optional
    company name.
-   **Item** --- project work item, contractor assignment, zone, due
    date, status, and submission details.
-   **Task** --- task associated with an item, including assigned site
    engineer, responsible consultant, status, and due date.
-   **Message** --- comments or messages between users, associated with
    an item or task, with an optional attachment field.

## Development notes

-   The project currently uses **SQLite** for local development.
-   Django's built-in development server is intended for local testing,
    not production hosting.
-   `core/tests.py` currently contains Django's test scaffold; add and
    run project-specific tests as the workflow is finalized.
-   Keep the virtual environment, local database, generated files, and
    secrets out of version control unless there is a deliberate,
    reviewed reason to include them.

## Security before publishing or deployment

Before pushing the project to a public repository or deploying it:

1.  **Remove secrets from source code.** The current development
    settings contain a hard-coded Django `SECRET_KEY`. Move it to an
    environment variable and rotate it if it has been exposed.
2.  Set `DEBUG = False` in production.
3.  Configure `ALLOWED_HOSTS` for the actual deployment domain.
4.  Do not commit real user passwords, private data, local database
    contents, uploaded attachments, or private network credentials.
5.  Review the repository contents before each push.

A public GitHub repository makes committed files visible to anyone.
Changing or deleting a secret in a later commit does not remove it from
Git history.

## Roadmap

Potential next steps for a more complete release:

-   Add a maintained dependency file such as `requirements.txt`.
-   Expand automated tests for authentication, role permissions, task
    status updates, and item submission/review.
-   Move environment-specific settings and secrets out of source code.
-   Document a safe demo-data setup for reviewers.
-   Configure production hosting, static files, media storage, and
    deployment security.

------------------------------------------------------------------------

## Project

**Name:** Bayyen\
**Focus:** Construction project coordination and progress visibility\
**Context:** Expo 2030 Riyadh challenge concept\
**Framework:** Django
