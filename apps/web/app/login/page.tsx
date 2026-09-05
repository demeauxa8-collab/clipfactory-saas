import Link from "next/link";
import type { Metadata } from "next";
import { ProductBrand } from "@/components/product/product-primitives";
import { LoginForm } from "./login-form";
import styles from "./login.module.css";

export const metadata: Metadata = {
  title: "Sign in",
  description:
    "Sign in to keep your ClipFactory campaign brief, source video and generated cuts together.",
  robots: { index: false, follow: false },
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string; auth?: string }>;
}) {
  const resolvedSearchParams = await searchParams;

  return (
    <main id="main-content" className={styles.page}>
      <header className={styles.chrome}>
        <ProductBrand />
        <p>Campaign workspace</p>
      </header>

      <section className={styles.workspace} aria-label="Sign in to ClipFactory">
        <div className={styles.sourceBay}>
          <div className={styles.sourceBayTopline}>
            <span className={styles.signal} aria-hidden="true" />
            <span>Source thread</span>
            <span className={styles.sourceBayMeta}>
              Campaign · Edit · Proof
            </span>
          </div>

          <div className={styles.sourceCopy}>
            <p className={styles.kicker}>Everything stays attached</p>
            <h2>Your edit keeps its place.</h2>
            <p>
              Campaign intent, transcript-grounded moments and final cuts stay
              on one continuous source thread.
            </p>
          </div>

          <div
            className={styles.sourceThread}
            aria-label="ClipFactory source workflow"
          >
            <div className={styles.sourceFile}>
              <div>
                <span>Source</span>
                <strong>Interview_master.mov</strong>
              </div>
              <span>18:42</span>
            </div>

            <div className={styles.timeline} aria-hidden="true">
              <span className={styles.timelineWave} />
              <span className={styles.timelineSelection} />
              <span className={styles.timelinePlayhead} />
            </div>

            <ol className={styles.threadSteps}>
              <li>
                <span aria-hidden="true" />
                <div>
                  <strong>Campaign brief</strong>
                  <small>The lens</small>
                </div>
              </li>
              <li>
                <span aria-hidden="true" />
                <div>
                  <strong>Source moments</strong>
                  <small>The evidence</small>
                </div>
              </li>
              <li>
                <span aria-hidden="true" />
                <div>
                  <strong>Final cuts</strong>
                  <small>The result</small>
                </div>
              </li>
            </ol>
          </div>

          <p className={styles.sourceFootnote}>
            Sign in to return to the same campaign, source and cut.
          </p>
        </div>

        <div className={styles.authPanel}>
          <div className={styles.authInner}>
            <header className={styles.authHeader}>
              <p className={styles.eyebrow}>
                <span aria-hidden="true" />
                Your edit is waiting
              </p>
              <h1>Continue to ClipFactory</h1>
              <p>
                Sign in to keep your campaign brief, source and generated cuts
                together.
              </p>
            </header>

            <div className={styles.formRegion}>
              <LoginForm searchParams={resolvedSearchParams} />
            </div>

            <p className={styles.terms}>
              By continuing, you agree to the{" "}
              <Link href="/legal/terms">Terms</Link> and{" "}
              <Link href="/legal/privacy">Privacy Policy</Link>.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
