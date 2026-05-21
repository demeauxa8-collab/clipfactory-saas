"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch, ApiError } from "@/lib/api";

type Campaign = { id: string; name: string };

export function NewCampaignForm() {
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const formData = new FormData(event.currentTarget);
    const payload = {
      name: String(formData.get("name") ?? "").trim(),
      audience: String(formData.get("audience") ?? "").trim(),
      niche: String(formData.get("niche") ?? "").trim(),
      tone: String(formData.get("tone") ?? "").trim(),
      goal: String(formData.get("goal") ?? "").trim(),
      avoid_topics: String(formData.get("avoid_topics") ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      example_hooks: String(formData.get("example_hooks") ?? "")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
    };

    try {
      const created = await apiFetch<Campaign>("/campaigns", {
        method: "POST",
        json: payload,
      });
      router.push(`/app/campaigns/${created.id}`);
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.code ?? err.message);
      } else {
        setError("unexpected_error");
      }
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <Field label="Campaign name" name="name" required placeholder="Founder lessons Q2" maxLength={80} />
      <Field
        label="Target audience"
        name="audience"
        placeholder="Solo SaaS founders learning to do paid ads"
        maxLength={400}
      />
      <Field label="Niche" name="niche" placeholder="bootstrapped SaaS" maxLength={120} />
      <Field label="Tone" name="tone" placeholder="direct, no-fluff, slightly contrarian" maxLength={120} />
      <Field label="Goal" name="goal" placeholder="Drive newsletter signups via shorts" maxLength={400} />
      <Field
        label="Avoid topics (comma-separated)"
        name="avoid_topics"
        placeholder="politics, religion, crypto pumps"
        maxLength={400}
      />
      <Textarea
        label="Example hooks (one per line)"
        name="example_hooks"
        placeholder="They said it was impossible. Here is how I did it.\nMy biggest mistake the first year."
        rows={5}
      />

      <div className="flex items-center gap-3 pt-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create campaign"}
        </Button>
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </form>
  );
}

function Field({
  label,
  name,
  required,
  placeholder,
  maxLength,
}: {
  label: string;
  name: string;
  required?: boolean;
  placeholder?: string;
  maxLength?: number;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={name} className="text-sm font-medium">
        {label}
        {required && <span className="text-red-600"> *</span>}
      </label>
      <Input id={name} name={name} required={required} placeholder={placeholder} maxLength={maxLength} />
    </div>
  );
}

function Textarea({
  label,
  name,
  rows,
  placeholder,
}: {
  label: string;
  name: string;
  rows: number;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={name} className="text-sm font-medium">{label}</label>
      <textarea
        id={name}
        name={name}
        rows={rows}
        placeholder={placeholder}
        className="flex w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm placeholder:text-[var(--color-muted-foreground)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-ring)]"
      />
    </div>
  );
}
