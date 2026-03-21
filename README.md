# Expense Tracker Backend

A FastAPI-based backend for personal expense tracking with support for multiple accounts, income/expense transactions, and transfers.

## Tech Stack

- **Framework**: FastAPI (async)
- **Database**: PostgreSQL (Supabase)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Package Manager**: uv

## Project Structure

```
expense-tracker-backend/
├── app/
│   ├── api/                 # API route handlers
│   │   ├── accounts.py      # Account endpoints
│   │   ├── categories.py    # Category endpoints
│   │   ├── transactions.py  # Transaction endpoints
│   │   └── deps.py          # Dependencies (DB session, Supabase JWT)
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── account.py
│   │   ├── category.py
│   │   └── transaction.py
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── account_schema.py
│   │   ├── category_schema.py
│   │   └── transaction_schema.py
│   ├── services/            # Business logic layer
│   │   ├── account_service.py
│   │   ├── category_service.py
│   │   ├── transaction_service.py
│   │   └── user_service.py
│   ├── database/            # Database configuration
│   │   ├── base.py          # SQLAlchemy Base
│   │   └── session.py       # Async session management
│   ├── config.py            # Environment settings
│   └── main.py              # FastAPI app entry point
├── alembic/                 # Database migrations
├── .env                     # Environment variables
└── pyproject.toml           # Dependencies
```

## Setup & Run

```bash
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start server
uv run uvicorn app.main:app --reload
```

Server runs at: `http://127.0.0.1:8000`  
API Docs: `http://127.0.0.1:8000/docs`

### Authentication (Supabase JWT)

Protected routes require `Authorization: Bearer <access_token>` from Supabase Auth.

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Project URL (e.g. `https://<ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Sent as `apikey` when fetching JWKS from `/auth/v1/keys` (required for RS256) |
| `SUPABASE_JWT_SECRET` | JWT secret from **Settings → API → JWT Secret**; required if access tokens use **HS256** |
| `SUPABASE_JWT_AUDIENCE` | Defaults to `authenticated` |

The server validates `aud` and `iss` (`{SUPABASE_URL}/auth/v1`), caches JWKS briefly, and auto-creates a `users` row on first request when the token is valid.

---

## Database Models

### User
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| email | String | Unique email |
| created_at | DateTime | Creation timestamp |

### Account
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Foreign key to users |
| name | String | Account name (e.g., "HDFC Savings") |
| type | Enum | `bank`, `cash`, `credit_card` |
| current_balance | Decimal | Current balance |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |

### Category
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Foreign key to users |
| name | String | Category name (e.g., "Food") |
| type | Enum | `expense`, `income` |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |

### Transaction
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Foreign key to users |
| amount | Decimal | Transaction amount |
| type | Enum | `expense`, `income`, `transfer` |
| from_account_id | UUID | Source account (for expense/transfer) |
| to_account_id | UUID | Destination account (for income/transfer) |
| category_id | UUID | Optional category |
| description | String | Optional description |
| transaction_date | DateTime | When transaction occurred |
| reference_hash | String | Unique hash for deduplication |
| created_at | DateTime | Creation timestamp |

---

## API Endpoints

### Accounts

#### Create Account
```
POST /api/accounts/create_account
```
**Request:**
```json
{
  "name": "HDFC Savings",
  "type": "bank",
  "initial_balance": 10000
}
```
**Response:** Account object with `id`, `current_balance`, etc.

#### Get All Accounts
```
GET /api/accounts/get_accounts
```
**Response:** List of account objects

---

### Categories

#### Create Category
```
POST /api/categories/create_category
```
**Request:** `{ "name": "Food", "type": "expense" }`  
**Response:** Category object

#### Get All Categories
```
GET /api/categories/get_categories
```
**Response:** List of category objects

---

### Transactions

#### Create Transaction
```
POST /api/transactions/create_transaction
```

**Expense Example** (deducts from account):
```json
{
  "amount": 500,
  "type": "expense",
  "transaction_date": "2026-02-23T10:00:00Z",
  "from_account_id": "<account_uuid>",
  "description": "Groceries"
}
```

**Income Example** (adds to account):
```json
{
  "amount": 2000,
  "type": "income",
  "transaction_date": "2026-02-23T11:00:00Z",
  "to_account_id": "<account_uuid>",
  "description": "Salary"
}
```

**Transfer Example** (moves between accounts):
```json
{
  "amount": 1500,
  "type": "transfer",
  "transaction_date": "2026-02-23T12:00:00Z",
  "from_account_id": "<source_account_uuid>",
  "to_account_id": "<destination_account_uuid>",
  "description": "ATM withdrawal"
}
```

---

## Service Layer Functions

### account_service.py

| Function | Parameters | Description |
|----------|------------|-------------|
| `create_account()` | db, user_id, name, account_type, initial_balance | Creates a new account for the user |
| `get_user_accounts()` | db, user_id | Returns all accounts belonging to the user |
| `update_balance()` | db, account_id, new_balance | Directly updates an account's balance |

### category_service.py

| Function | Parameters | Description |
|----------|------------|-------------|
| `create_category()` | db, user_id, name, category_type | Creates a category for the user |
| `get_user_categories()` | db, user_id | Lists categories for the user |

### user_service.py

| Function | Parameters | Description |
|----------|------------|-------------|
| `ensure_user()` | db, user_id, email | Inserts `users` row on first authenticated request if missing |

### transaction_service.py

| Function | Parameters | Description |
|----------|------------|-------------|
| `create_transaction()` | db, user_id, amount, transaction_type, transaction_date, from_account_id, to_account_id, category_id, description, reference_hash | Creates transaction and updates account balances atomically |

#### Transaction Logic (inside `create_transaction`):

```
┌─────────────────────────────────────────────────────────┐
│                  create_transaction()                   │
├─────────────────────────────────────────────────────────┤
│  BEGIN NESTED TRANSACTION (savepoint)                   │
│                                                         │
│  IF type == "expense":                                  │
│      from_account.current_balance -= amount             │
│                                                         │
│  ELIF type == "income":                                 │
│      to_account.current_balance += amount               │
│                                                         │
│  ELIF type == "transfer":                               │
│      from_account.current_balance -= amount             │
│      to_account.current_balance += amount               │
│                                                         │
│  INSERT transaction record                              │
│                                                         │
│  COMMIT (or ROLLBACK on any error)                      │
└─────────────────────────────────────────────────────────┘
```

All balance updates are **atomic** - if anything fails, the entire operation rolls back.

---

## Alembic Commands

```bash
# Generate migration after model changes
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

---

## Environment Variables (.env)

```
DATABASE_HOST=your-db-host
DATABASE_PORT=5432
DATABASE_NAME=postgres
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password
DATABASE_URL=postgresql://user:pass@host:port/db

# Optional pool settings
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
```
