# Acme Platform Guide

## Plans
Webhook **retries** are included on every plan, including the free plan. The
**dead-letter queue** is a paid feature and is not part of the free plan.

## Data residency
The EU data residency tier stores all customer data in **Frankfurt**, **Dublin**,
and **Paris**. Choosing the EU tier disables data replication to US regions.

## Single sign-on
SSO group mapping assigns users to roles based on their identity-provider groups.
When a user matches both a mapped group and a **custom role**, the custom role
takes precedence over the group default.

## Audit logs
Audit logs are retained for **2 years** on the enterprise plan and 90 days on all
other plans. Retention is not configurable.
