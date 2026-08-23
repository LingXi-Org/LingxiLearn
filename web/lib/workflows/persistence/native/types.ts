import type { ExtractTablesWithRelations } from "drizzle-orm";
import type { PgTransaction } from "drizzle-orm/pg-core";
import type { PostgresJsQueryResultHKT } from "drizzle-orm/postgres-js";
import type { Edge } from "reactflow";
import type { db } from "@/lib/db";
import type * as schema from "@/lib/db/schema";
import type {
	BlockState,
	Loop,
	Parallel,
} from "@/lib/workflows/domain/workflow";

export type DbOrTx =
	| typeof db
	| PgTransaction<
			PostgresJsQueryResultHKT,
			typeof schema,
			ExtractTablesWithRelations<typeof schema>
	  >;

export interface NormalizedWorkflowData {
	blocks: Record<string, BlockState>;
	edges: Edge[];
	loops: Record<string, Loop>;
	parallels: Record<string, Parallel>;
	isFromNormalizedTables: boolean;
}
