import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { loginUrl } from "@/lib/api";

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center bg-gradient-to-b from-accent/60 to-background p-6">
      <div className="w-full max-w-sm space-y-6 rounded-2xl border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary text-xl font-bold text-primary-foreground">
          S
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Welcome to Stanley</h1>
          <p className="text-sm text-muted-foreground">
            See what everyone is working on and what&apos;s stuck, straight from GitLab. Sign in with your GitLab
            account. You can only see and do what GitLab already lets you.
          </p>
        </div>
        <a href={loginUrl()} className={cn(buttonVariants({ size: "lg" }), "w-full")}>
          Sign in with GitLab
        </a>
      </div>
    </main>
  );
}
