import { describe, expect, it } from "vitest";
import {
  SETTINGS_SECTION_REGISTRY,
  WORKSPACE_SETTINGS_ITEMS,
} from "@/components/settings/navigation";
import {
  allNavigationItems,
  sectionConfig,
} from "@/app/workspace/[workspaceId]/settings/navigation";

describe("unified settings navigation", () => {
  it("groups settings by the scope they affect", () => {
    expect(sectionConfig).toEqual([
      { key: "account", title: "账户" },
      { key: "workspace", title: "工作区" },
      { key: "organization", title: "组织" },
      { key: "platform", title: "平台" },
    ]);
  });

  it("keeps account, workspace, organization, and platform settings in one catalog", () => {
    expect(allNavigationItems).toHaveLength(24);
    expect(allNavigationItems.find(({ id }) => id === "general")?.label).toBe("常规");
    expect(allNavigationItems.find(({ id }) => id === "mcp")?.label).toBe("MCP 工具");
    expect(allNavigationItems.find(({ id }) => id === "organization")?.label).toBe("成员");
  });

  it("orders each scope around its primary settings", () => {
    const idsForSection = (section: (typeof sectionConfig)[number]["key"]) =>
      allNavigationItems
        .filter((item) => item.section === section)
        .sort((left, right) => left.order - right.order)
        .map(({ id }) => id);

    expect(idsForSection("account")).toEqual([
      "general",
      "billing",
      "desktop",
      "browser",
      "terminal",
    ]);
    expect(idsForSection("workspace")).toEqual([
      "teammates",
      "secrets",
      "mcp",
      "custom-tools",
      "byok",
      "inbox",
      "workflow-mcp-servers",
      "recently-deleted",
    ]);
    expect(idsForSection("organization")).toEqual([
      "organization",
      "custom-blocks",
      "forks",
      "access-control",
      "audit-logs",
      "whitelabeling",
      "sso",
      "sessions",
      "data-retention",
      "data-drains",
    ]);
    expect(idsForSection("platform")).toEqual(["self-host"]);
  });

  it("derives every unified item from exactly one registry entry", () => {
    expect(allNavigationItems).toHaveLength(
      SETTINGS_SECTION_REGISTRY.filter(({ unified }) => unified).length,
    );
    for (const item of allNavigationItems) {
      expect(
        SETTINGS_SECTION_REGISTRY.filter(
          ({ unified }) => unified?.id === item.id,
        ),
      ).toHaveLength(1);
    }
  });

  it("shares labels, icons, and docs links with plane projections", () => {
    const unifiedForks = allNavigationItems.find(({ id }) => id === "forks");
    const workspaceForks = WORKSPACE_SETTINGS_ITEMS.find(
      ({ id }) => id === "forks",
    );

    expect(workspaceForks?.label).toBe(unifiedForks?.label);
    expect(workspaceForks?.icon).toBe(unifiedForks?.icon);
    expect(workspaceForks?.docsLink).toBe(unifiedForks?.docsLink);
  });
});
