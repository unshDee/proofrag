# Acme API Reference

## Authentication
The Acme CLI supports two authentication methods: static **API keys** and the
**OAuth device flow** for interactive login. Service accounts must use API keys.

### Rotating an API key without downtime
To rotate a key with zero downtime: create a new key in the dashboard, deploy it
to your services, verify traffic is flowing on the new key, then revoke the old
key. Never revoke before deploying the replacement.

## Batch endpoint
The batch endpoint accepts up to **10 MB** per request. Larger jobs must be split
client-side. Each batch may contain at most 500 items.

## Webhooks
Webhooks are delivered at least once. Failed deliveries are retried with
exponential backoff for up to 24 hours. A **dead-letter queue** captures events
that exhaust all retries, but the dead-letter queue is only available on paid plans.
