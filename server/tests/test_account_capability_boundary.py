from lingxilearn.main import app

REMOVED_PLACEHOLDER_PATHS = {
    "/api/settings/allowed-integrations",
    "/api/settings/allowed-providers",
    "/api/settings/voice",
    "/api/telemetry",
    "/api/users/me/profile",
    "/api/organizations",
    "/api/billing",
    "/api/billing/invoices",
    "/api/billing/portal",
    "/api/billing/credits",
    "/api/billing/switch-plan",
    "/api/billing/update-cost",
    "/api/usage",
    "/api/users/me/usage-limits",
    "/api/users/me/subscription/{subscription_id}/transfer",
    "/api/v2/billing/status",
    "/api/v2/billing/logs",
    "/api/users/me/settings",
    "/api/users/me/usage-logs",
    "/api/users/me/usage-logs/export",
}


def test_unowned_account_capabilities_have_no_registered_routes() -> None:
    paths = set(app.openapi()["paths"])
    assert paths.isdisjoint(REMOVED_PLACEHOLDER_PATHS), sorted(
        paths.intersection(REMOVED_PLACEHOLDER_PATHS)
    )


def test_account_router_keeps_only_lingxilearn_owned_surfaces() -> None:
    paths = set(app.openapi()["paths"])
    assert paths.isdisjoint(REMOVED_PLACEHOLDER_PATHS)
