# Quote AI Configuration Permission Fix

## Approved Scope

The user approved restoring quote AI configuration access to super administrators and account UID `A`, while denying other accounts. Stored API keys must never be returned. Failed configuration reads must be visible and save errors must be red, including errors without the word "失败".

## Design

- Reuse `require_business_admin` for GET and POST `/api/ai-config`. Its predicate already allows super administrators or exact UID `A`. Do not change `require_super_admin` or other route policies.
- Generalize the shared business-admin denial message to describe a management operation, not only permission assignment.
- Hide the quote AI configuration entry for other users using existing `isBusinessAdmin`. Mount the dialog only when permitted and open.
- Keep API-key redaction and blank-key preservation unchanged.
- Replace string-based error coloring with explicit success/error feedback. Show failed reads, disable save until configuration loads, provide read retry, ignore late reads after unmount and clean up delayed close timers.
- No model inference, connection testing, credential changes or global role expansion during verification.

## Verification

Isolated API tests cover account A, super administrators, other roles, spoofed display names, broad business grants, no authentication, key redaction/preservation and unchanged super-admin-only boundaries. Browser tests cover entry visibility, read failure, save failure, retry and stale-read cleanup on desktop/mobile. Run TypeScript, targeted ESLint and existing management/reference regressions before pushing the approved branch and providing cloud update commands.
