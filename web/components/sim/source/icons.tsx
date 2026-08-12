import type { SVGProps } from 'react'

/**
 * SimArrowUp icon component
 * @param props - SVG properties including className, fill, etc.
 */
export function SimArrowUp(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width='24'
      height='24'
      viewBox='-1 -2 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='1.55'
      strokeLinecap='round'
      strokeLinejoin='round'
      xmlns='http://www.w3.org/2000/svg'
      aria-hidden='true'
      {...props}
    >
      <path d='M4 9.25L10.25 3L16.5 9.25' />
      <path d='M10.25 3V17.5' />
    </svg>
  )
}

/**
 * SimPlus icon component
 * @param props - SVG properties including className, fill, etc.
 */
export function SimPlus(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width='24'
      height='24'
      viewBox='-1 -2 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='1.55'
      strokeLinecap='round'
      strokeLinejoin='round'
      xmlns='http://www.w3.org/2000/svg'
      aria-hidden='true'
      {...props}
    >
      <path d='M10.25 3V17.5' />
      <path d='M3 10.25H17.5' />
    </svg>
  )
}
