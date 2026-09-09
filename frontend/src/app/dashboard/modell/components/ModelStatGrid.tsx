import { Brain, Database, Eye, Cpu, TrendingUp } from "lucide-react";
import { accuracyTextClass } from "../helpers";
import type { ModelInfo, VisionStatus } from "../types";
import { StatCard } from "./StatCard";

interface ModelStatGridProps {
  info: ModelInfo | null;
  vision: VisionStatus;
  acc: number;
}

export function ModelStatGrid({ info, vision, acc }: ModelStatGridProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      <StatCard
        icon={<Cpu className="w-5 h-5 text-brand-600 dark:text-brand-300" />}
        label="Genauigkeit"
        value={info?.has_model ? `${(acc * 100).toFixed(1)}%` : "—"}
        sub={info?.has_model ? "Cross-Validation" : "Nicht trainiert"}
        valueClass={info?.has_model ? accuracyTextClass(acc) : "text-muted-foreground"}
      />
      <StatCard
        icon={<Database className="w-5 h-5 text-info" />}
        label="Samples"
        value={String(info?.total_samples ?? 0)}
        sub={`${info?.classes ?? 0} Kontenklassen`}
      />
      <StatCard
        icon={<Brain className="w-5 h-5 text-success" />}
        label="Gedächtnis"
        value={String(info?.memory_count ?? 0)}
        sub="Exakte Treffer"
      />
      <StatCard
        icon={<TrendingUp className="w-5 h-5 text-warning" />}
        label="Korrekturen"
        value={String(info?.correction_count ?? 0)}
        sub="Verfügbar"
      />
      <StatCard
        icon={<Eye className="w-5 h-5 text-brand-600 dark:text-brand-300" />}
        label="Vision"
        value={vision.available ? (vision.is_cloud ? "Cloud" : "Lokal") : "—"}
        sub={vision.model_name ?? "Nicht verbunden"}
        valueClass={vision.available ? "text-brand-600 dark:text-brand-300" : "text-muted-foreground"}
      />
    </div>
  );
}
