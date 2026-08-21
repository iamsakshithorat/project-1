# Multi-Account AWS Governance Setup
### Using AWS Organizations & Service Control Policies (SCPs)

**Role:** Cloud Governance Engineer
**Objective:** Implement centralized governance across Dev, Test, and Prod AWS accounts to enforce security, cost, and compliance policies.

---


## 1. Problem Statement

The organization runs multiple AWS accounts (Dev, Test, Prod) with no centralized restrictions. This has led to:

- Developers launching **expensive/oversized EC2 instances** in non-production accounts.
- **Inconsistent security posture** — CloudTrail can be disabled by any user with sufficient IAM permissions, destroying the audit trail.
- **No region control** — resources can be deployed anywhere, increasing cost, latency, and compliance risk.

**Goal:** Use AWS Organizations + SCPs to enforce these controls centrally, at the OU level, so no IAM policy inside a member account can override them.

---

## 2. Architecture: AWS Organizations Structure

```
                    ┌─────────────────────────┐
                    │   Management Account     │
                    │                          │
                    └────────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                          │
   ┌────▼──────┐          ┌──────▼──────┐            ┌──────▼──────┐
   │Dev-Team-OU│          │Test-Team-OU │            │Prob-Team-OU │
   └────┬──────┘          └──────┬──────┘            └──────┬──────┘
        │                        │                          │
  ┌─────▼──────┐          ┌──────▼──────┐            ┌──────▼──────┐
  │ dev-account│          │ test-account│            │ prob-account│
  └────────────┘          └─────────────┘            └─────────────┘
```

**Why OUs instead of applying SCPs directly to accounts?**
OUs let policy scale with the org. New Dev accounts automatically inherit Dev OU policies without manual re-attachment — this is the core of "centralized governance."

---

## 3. Step-by-Step Implementation

### Step 1 — Enable AWS Organizations
Enabled AWS Organizations with **"all features"** mode (required for SCPs — consolidated-billing-only mode does not support them).

### Step 2 — Create Organizational Units
Created three OUs under Root:

| OU Name | Purpose |
|---|---|
| `Dev-Team-OU` | Sandbox/development workloads — most restrictive on cost, least restrictive on experimentation |
| `Test-Team-OU` | QA/staging — mirrors prod controls but allows more teardown/rebuild activity |
| `Prob-Team-OU` | Live/production-equivalent workloads — strictest controls |

### Step 3 — Create Member Accounts & Move into OUs
Created three member accounts via **Organizations → Add an AWS account → Create an AWS account**, then moved each into its respective OU:

| Account | OU | Purpose |
|---|---|---|
| `dev-account` | Dev-Team-OU | Development sandbox |
| `test-account` | Test-Team-OU | QA / staging |
| `prob-account` | Prob-Team-OU | Production-equivalent |

Final structure verified via the Organizations console hierarchy view — see `screenshots/ou-structure.png`.

### Step 4 — Enable SCPs
Enabled **Service control policies** as a policy type in Organizations → Policies.

### Step 5 — Create & Attach SCPs
Created three SCPs (JSON in `/scp-policies`) and attached them:

| Policy | Attached To | File |
|---|---|---|
| Deny Large EC2 Instances | `Dev-Team-OU` only | `deny-large-ec2-instances-dev.json` |
| Deny Disabling CloudTrail | Organization Root (applies to all OUs) | `deny-disable-cloudtrail.json` |
| Restrict Approved Regions | Organization Root (applies to all OUs) | `restrict-approved-regions.json` |

---

## 4. Policy Logic Explained

### 4.1 Deny Large EC2 Instance Types (Dev-Team-OU only)
```json
"Condition": {
  "ForAnyValue:StringNotLike": {
    "ec2:InstanceType": ["t2.micro","t2.small","t3.micro","t3.small","t3.medium"]
  }
}
```
**Logic:** Deny `ec2:RunInstances` unless the requested instance type matches an approved "small" list. IAM permissions inside the Dev account are capped, not replaced — even a Dev IAM Admin cannot exceed this boundary, because SCPs are evaluated before IAM policies.

### 4.2 Deny Disabling CloudTrail (Organization Root — all accounts)
```json
"Action": ["cloudtrail:StopLogging","cloudtrail:DeleteTrail","cloudtrail:UpdateTrail","cloudtrail:PutEventSelectors","cloudtrail:RemoveTags"]
```
**Logic:** Blocks the specific API calls that would stop, delete, modify, or de-scope CloudTrail logging across every account in the organization. CloudTrail is the backbone of incident response and compliance audits — if it can be disabled, every other control becomes unverifiable.

### 4.3 Restrict Approved Regions (Organization Root — all accounts)
```json
"Condition": {
  "StringNotEquals": { "aws:RequestedRegion": ["us-east-1","us-east-2"] }
}
```
**Logic:** Denies most actions outside the approved regions (global services like IAM, Route 53, CloudFront, STS are excluded via `NotAction` since they aren't region-scoped). Prevents shadow-IT deployments in unapproved regions and keeps cost/monitoring centralized.

---

## 5. Validation — Proof of Enforcement

Logged into `dev-account`  via **Switch Role** (`OrganizationAccountAccessRole`) from the management account, then attempted two restricted actions.


##  Screen Shot:
 # 1:ou-structure:
 
 # 2:scp-policies-list
 <img width="1912" height="970" alt="Image" src="https://github.com/user-attachments/assets/eca12d27-904d-4b00-8a9c-9c567c66eaf1" />

 # 3:policy-attachment
 <img width="1911" height="978" alt="Image" src="https://github.com/user-attachments/assets/d6a97867-04dc-4721-bfe2-067974e17c89" />

 # 4:region-restriction-denied
 <img width="1919" height="970" alt="Image" src="https://github.com/user-attachments/assets/2de46773-f885-483a-a107-3127e87f4e21" />

 # 5:ec2-large-instance-denied
<img width="1913" height="975" alt="Image" src="https://github.com/user-attachments/assets/8e9f233a-fa3b-4166-b52b-4b89b5456cfb" />

 

### Test 1 — Region Restriction (unapproved region: Asia Pacific / Sydney)
Simply loading the EC2 dashboard while the session's region was set to **Asia Pacific (Sydney)** — outside the approved `us-east-1` / `us-east-2` list — triggered **"Access denied"** on nearly every EC2 resource type (Elastic IPs, Load balancers, Security groups, Snapshots, Volumes, etc.), confirming the `RestrictApprovedRegions` SCP was actively enforced without any explicit action needed.

### Test 2 — Large EC2 Instance Type (Dev account, approved region)
Switched to **US East (Ohio)** (an approved region) and attempted to launch an `m5.xlarge` instance (outside the allowed small-instance list). Result:

```
| Test | Region | Action | Result |
|---|---|---|---|
| 1 | Asia Pacific (Sydney) — not approved | Load EC2 resources | Access denied (region SCP) |
| 2 | US East (Ohio) — approved | Launch `m5.xlarge` instance | Access denied, explicit SCP deny (`p-7jiv1i61`) |

### Screen Shot:


---

## 6. Risk Mitigation Strategy

| Risk (Before Governance) | Mitigation (After SCPs) |
|---|---|
| Uncontrolled cloud spend from oversized Dev instances | Instance-type allow-list caps maximum spend per instance |
| Audit trail can be silently disabled | CloudTrail management actions denied org-wide |
| Resources sprawled across regions | Hard region allow-list at the SCP layer |
| Inconsistent policy enforcement per-account | OU-based inheritance — new accounts automatically inherit guardrails |
| Over-privileged IAM roles able to bypass restrictions | SCPs set a hard ceiling that no IAM policy, including AdministratorAccess, can exceed |

---

## 7. Governance Benefits

- **Centralized control:** Managed entirely from the management account; individual account owners cannot override guardrails.
- **Preventive, not just detective:** SCPs block the action at request time, unlike alerting that fires after the fact.
- **Scalable:** Future accounts placed in an OU automatically inherit its policies — no manual re-application.
- **Cost predictability:** Instance-type restrictions in Dev directly cap runaway compute spend.
- **Audit-ready compliance posture:** Guaranteed CloudTrail logging + region restriction produces a clean audit trail.
- **Separation of duties:** Developers retain IAM freedom within their sandbox; governance boundaries are enforced independently.

---


