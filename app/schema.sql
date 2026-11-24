-- All CareGuard tables. Safe to run more than once.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS plans (
    id              text PRIMARY KEY,            -- 'basic', 'plus', 'senior'
    name            text    NOT NULL,
    sum_insured     integer NOT NULL,            -- rupees
    policy_doc_file text    NOT NULL             -- file name in data/policies/
);

CREATE TABLE IF NOT EXISTS members (
    id                text PRIMARY KEY,          -- 'M001'
    name              text    NOT NULL,
    api_key           text    NOT NULL UNIQUE,
    plan_id           text    NOT NULL REFERENCES plans (id),
    policy_start_date date    NOT NULL,
    age               integer NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id               text PRIMARY KEY,           -- 'CLM-1001'
    member_id        text    NOT NULL REFERENCES members (id),
    hospital         text    NOT NULL,
    procedure        text    NOT NULL,
    amount_claimed   integer NOT NULL,           -- rupees
    amount_approved  integer,                    -- rupees; NULL while pending
    status           text    NOT NULL
        CHECK (status IN ('approved', 'partially_approved', 'rejected', 'pending')),
    rejection_reason text,
    submitted_on     date    NOT NULL
);
CREATE INDEX IF NOT EXISTS claims_member_id_idx ON claims (member_id);

CREATE TABLE IF NOT EXISTS review_tickets (
    id         serial PRIMARY KEY,
    member_id  text NOT NULL REFERENCES members (id),
    claim_id   text REFERENCES claims (id),      -- NULL for "not found in policy" tickets
    reason     text NOT NULL,
    status     text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_by text,
    decided_at timestamptz
);

CREATE TABLE IF NOT EXISTS policy_chunks (
    id            serial PRIMARY KEY,
    plan_id       text NOT NULL,                 -- a plans.id, or 'common'
    section_title text NOT NULL,
    text          text NOT NULL,
    embedding     vector(384),
    source_file   text NOT NULL,
    sha256        text NOT NULL
);

CREATE TABLE IF NOT EXISTS request_logs (
    id                  serial PRIMARY KEY,
    request_id          text    NOT NULL,
    member_id           text,
    question_redacted   text    NOT NULL,
    tools_called        text[]  NOT NULL DEFAULT '{}',
    retrieval_top_score real,
    refused             boolean NOT NULL,
    latency_ms          integer NOT NULL,
    tokens_in           integer,
    tokens_out          integer,
    created_at          timestamptz NOT NULL DEFAULT now()
);
