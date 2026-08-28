import Image from 'next/image'
import Link from 'next/link'

export default function HomePage() {
  return (
    <main className='landing-shell'>
      <nav className='landing-nav'>
        <Image
          alt='LingxiLearn'
          height={36}
          src='/brand/lingxi/wordmark-on-light.svg'
          width={150}
        />
        <Link className='button ghost' href='/login'>
          Sign in
        </Link>
      </nav>
      <section className='landing-hero'>
        <span className='eyebrow'>A workspace that learns with you</span>
        <h1>Turn curiosity into durable understanding.</h1>
        <p>
          Lingxi plans the work, gathers evidence, creates artifacts, and keeps every decision
          visible.
        </p>
        <div className='hero-actions'>
          <Link className='button primary large' href='/workspace'>
            Enter your workspace
          </Link>
          <Link href='/workspace'>Start a learning task</Link>
        </div>
      </section>
      <section className='capability-grid'>
        <article>
          <span>01</span>
          <h2>Agent tasks</h2>
          <p>Long-running learning work with a durable, inspectable trail.</p>
        </article>
        <article>
          <span>02</span>
          <h2>Artifacts</h2>
          <p>Sources and outputs live together in one coherent library.</p>
        </article>
        <article>
          <span>03</span>
          <h2>Skills</h2>
          <p>Capture the methods you want your learning agent to reuse.</p>
        </article>
      </section>
    </main>
  )
}
