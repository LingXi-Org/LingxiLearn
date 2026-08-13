import type {
  AnyApiRouteContract,
  ContractBodyInput,
  ContractHeadersInput,
  ContractJsonResponse,
  ContractParamsInput,
  ContractQueryInput,
} from '@/lib/api/contracts'
import { lingxiNotIntegratedError } from '@/lib/lingxi/capabilities'

type MaybeField<Key extends string, Value> = [Value] extends [undefined]
  ? { [K in Key]?: never }
  : { [K in Key]: Value }

export type ApiClientRequest<C extends AnyApiRouteContract> = MaybeField<
  'params',
  ContractParamsInput<C>
> &
  MaybeField<'query', ContractQueryInput<C>> &
  MaybeField<'body', ContractBodyInput<C>> &
  MaybeField<'headers', ContractHeadersInput<C>> & {
    signal?: AbortSignal
  }

export interface ApiRawRequestOptions {
  cache?: RequestCache
  headers?: Record<string, string>
}

function routePath(contract: AnyApiRouteContract, input: object): string {
  const params = 'params' in input && input.params && typeof input.params === 'object'
    ? (input.params as Record<string, unknown>)
    : {}
  return contract.path.replace(/\[\[?(?:\.\.\.)?([^\][]+)\]\]?/g, (_match, key: string) =>
    encodeURIComponent(String(params[key] ?? key))
  )
}

/**
 * The imported browser components keep their strongly typed Sim contracts.
 * LingxiGraph has a deliberately smaller API, so every Sim-owned contract is
 * rejected locally before fetch.
 */
export async function requestJson<C extends AnyApiRouteContract>(
  contract: C,
  input: ApiClientRequest<C>
): Promise<ContractJsonResponse<C>> {
  throw lingxiNotIntegratedError(contract.method, routePath(contract, input))
}

export async function requestRaw<C extends AnyApiRouteContract>(
  contract: C,
  input: ApiClientRequest<C>,
  _options: ApiRawRequestOptions = {}
): Promise<Response> {
  throw lingxiNotIntegratedError(contract.method, routePath(contract, input))
}
