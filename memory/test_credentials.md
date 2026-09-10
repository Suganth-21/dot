# DOT — Demo Accounts (frontend-only, no passwords)

Login page: `/login` — click a demo account (one-click quick login, no password entry).
There is NO real auth backend; auth is a Zustand store persisted to localStorage.

| Role         | Portal              | Entity            | Home route            |
|--------------|---------------------|-------------------|-----------------------|
| RETAILER     | Pharmacy Portal     | Apollo Pharmacy — T. Nagar (ph_1) | /pharmacy/dashboard   |
| DISTRIBUTOR  | Distributor Portal  | Sunrise Pharma Distributors (dist_1) | /distributor/dashboard |
| PICKUP_AGENT | Pickup Agent App    | Ravi Kumar (agent_1) | /agent/today          |
| MANUFACTURER | Manufacturer Portal | Cipla Ltd. (mfr_1) | /manufacturer/dashboard |
| REGULATOR    | Drug Controller     | CDSCO — Tamil Nadu (reg_1) | /regulator/dashboard  |

Patient Shield is public: `/verify` (no login).

data-testids for quick login buttons:
- `quick-login-retailer`, `quick-login-distributor`, `quick-login-pickup_agent`,
  `quick-login-manufacturer`, `quick-login-regulator`
