import { JsonLd } from '@/app/(landing)/components/json-ld'

const SITE_URL = 'https://lingxilearn.cn'

const PRICING_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: '灵犀智学价格',
  url: `${SITE_URL}/pricing`,
  description: '灵犀智学学习工作台的服务方案。',
  isPartOf: { '@type': 'WebSite', name: '灵犀智学', url: SITE_URL },
  offers: [
    { '@type': 'Offer', name: '开放版', price: '0', priceCurrency: 'CNY' },
    { '@type': 'Offer', name: '成长版', price: '19', priceCurrency: 'CNY' },
    { '@type': 'Offer', name: '团队版', price: '49', priceCurrency: 'CNY' },
  ],
}

export function PricingStructuredData() {
  return <JsonLd data={PRICING_JSON_LD} />
}
