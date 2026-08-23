import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { member, permissions } from "@/lib/db/schema";
import { isOrgAdminRole, type PermissionType } from "./predicates";

export * from "./predicates";

/**
 * Resolves the effective workspace permission under the governance inheritance
 * model: the owners/admins of the organization that owns the workspace are
 * derived workspace admins. Returns the higher of any explicit grant and the
 * org-admin derivation.
 *
 * The workspace owner is intentionally NOT a special case: every owner already
 * holds an explicit `admin` row in `permissions` (added at creation, verified
 * across all production workspaces), so the lookup below already grants them
 * admin. `workspace.ownerId` is a lifecycle anchor, not a permission input.
 *
 * Single source of truth for workspace-permission resolution. Native application
 * services and realtime authorization both consume this module instead of
 * maintaining parallel permission inheritance rules.
 */
export async function resolveEffectiveWorkspacePermission(
	userId: string,
	workspaceId: string,
	workspaceOrganizationId: string | null,
	executor: Pick<typeof db, "select"> = db,
	options?: { forUpdate?: boolean },
): Promise<PermissionType | null> {
	const permissionQuery = executor
		.select({ permissionType: permissions.permissionType })
		.from(permissions)
		.where(
			and(
				eq(permissions.userId, userId),
				eq(permissions.entityType, "workspace"),
				eq(permissions.entityId, workspaceId),
			),
		);
	const [permissionRow] = options?.forUpdate
		? await permissionQuery.for("update").limit(1)
		: await permissionQuery.limit(1);

	const explicit =
		(permissionRow?.permissionType as PermissionType | undefined) ?? null;

	if (workspaceOrganizationId && explicit !== "admin") {
		const memberQuery = executor
			.select({ role: member.role })
			.from(member)
			.where(
				and(
					eq(member.userId, userId),
					eq(member.organizationId, workspaceOrganizationId),
				),
			);
		const [memberRow] = options?.forUpdate
			? await memberQuery.for("update").limit(1)
			: await memberQuery.limit(1);
		if (isOrgAdminRole(memberRow?.role)) {
			return "admin";
		}
	}

	return explicit;
}
