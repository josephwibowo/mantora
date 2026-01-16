import type { Cast } from "../api/types";
import { TableCast } from "./TableCast";

type Props = {
  cast: Cast;
  onStepClick?: (stepId: string) => void;
};

/**
 * Renders a cast artifact based on its kind.
 * Per DEC-V0-CASTS-EXPLICIT-TOOLS: casts are explicit observer-native tools.
 * Per PIT-HEURISTIC-UI: do not guess casts from queries; rely on explicit tools.
 */
export function CastRenderer({ cast, onStepClick }: Props) {
  switch (cast.kind) {
    case "table":
      return <TableCast cast={cast} onStepClick={onStepClick} />;
    default:
      return null;
  }
}
