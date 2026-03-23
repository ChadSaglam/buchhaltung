import { Sidebar } from "@/components/layout/Sidebar";
import { MobileNav } from "@/components/layout/MobileNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <div className="hidden md:block">
        <Sidebar />
      </div>
      <MobileNav />
      <main className="transition-all duration-300 md:ml-[var(--sidebar-width)] p-6 lg:p-8">
        {children}
      </main>
    </div>
  );
}
