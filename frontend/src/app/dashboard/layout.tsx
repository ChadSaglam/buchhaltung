import { Sidebar } from "@/components/layout/Sidebar";
import { MobileNav } from "@/components/layout/MobileNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <MobileNav />
      <main className="md:ml-[260px] p-6 md:p-8 pb-20 md:pb-8">
        {children}
      </main>
    </div>
  );
}
