import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { loginUrl } from "@/lib/api";

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>GitLab-Integrated PM Tool</CardTitle>
          <CardDescription>
            Sign in with your GitLab account. Your access here always mirrors what you can
            already see and do in GitLab.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <a href={loginUrl()} className={cn(buttonVariants(), "w-full")}>
            Sign in with GitLab
          </a>
        </CardContent>
      </Card>
    </main>
  );
}
