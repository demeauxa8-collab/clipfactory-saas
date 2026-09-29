import Link from "next/link";

export function MarketingBrand() {
  return (
    <Link href="/" className="marketing-brand" aria-label="ClipFactory home">
      <span className="marketing-brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>ClipFactory</span>
    </Link>
  );
}
