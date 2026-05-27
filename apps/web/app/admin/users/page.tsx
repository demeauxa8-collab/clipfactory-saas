import { Container } from "@/components/ui/container";
import { adminFetch } from "@/lib/admin-api";

type User = {
  user_id: string;
  email: string;
  full_name: string | null;
  is_admin: boolean;
  plan_code: string | null;
  sub_status: string | null;
  credits_balance: number;
  jobs_total: number;
  created_at: string;
};

export default async function AdminUsersPage() {
  let users: User[] = [];
  let error: string | null = null;
  try {
    users = await adminFetch<User[]>("/admin/users?limit=100");
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown_error";
  }

  return (
    <Container className="py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Users ({users.length})</h1>
      {error && (
        <div className="mt-4 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-muted)] p-3 text-sm text-[var(--color-foreground)]">
          {error}
        </div>
      )}
      <div className="pro-card mt-6 overflow-x-auto rounded-lg">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Credits</th>
              <th className="px-4 py-3 text-right">Jobs</th>
              <th className="px-4 py-3">Joined</th>
              <th className="px-4 py-3">Admin</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {users.map((u) => (
              <tr key={u.user_id} className="transition-colors duration-200 hover:bg-white/[0.035]">
                <td className="px-4 py-3 font-mono">{u.email}</td>
                <td className="px-4 py-3">{u.plan_code ?? "—"}</td>
                <td className="px-4 py-3">{u.sub_status ?? "—"}</td>
                <td className="px-4 py-3 text-right tabular-nums">{u.credits_balance}</td>
                <td className="px-4 py-3 text-right tabular-nums">{u.jobs_total}</td>
                <td className="px-4 py-3 text-[var(--color-muted-foreground)]">
                  {new Date(u.created_at).toLocaleDateString("en-GB")}
                </td>
                <td className="px-4 py-3">{u.is_admin ? "yes" : ""}</td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--color-muted-foreground)]">No users yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Container>
  );
}
