import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/ui/container";

export default function NotFound() {
  return (
    <Container className="flex flex-1 flex-col items-center justify-center py-32 text-center">
      <p className="text-sm font-mono text-[var(--color-muted-foreground)]">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-2 text-[var(--color-muted-foreground)]">
        The page you are looking for moved, was removed, or never existed.
      </p>
      <Link href="/" className="mt-6">
        <Button>Back to home</Button>
      </Link>
    </Container>
  );
}
