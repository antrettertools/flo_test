export interface CapacityGroupResult {
  category: string;
  technology: string | null;
  region_ags: string | null;
  size_class: string | null;
  month: string | null;
  unit_count: number;
  capacity_kw_sum: number | null;
  storage_capacity_kwh_sum: number | null;
}

export interface CapacityTotalsResponse {
  as_of_date: string;
  include_decommissioned: boolean;
  group_by: string[];
  results: CapacityGroupResult[];
}

export interface CapacityAdditionsResponse {
  date_from: string | null;
  date_to: string | null;
  group_by: string[];
  results: CapacityGroupResult[];
}

export interface RegionOut {
  ags: string;
  level: string;
  name: string;
  parent_ags: string | null;
}

export interface TechnologyMeta {
  technology: string;
  category: string;
  is_renewable: boolean | null;
}

export interface SizeClassMeta {
  category: string;
  size_classes: string[];
}

export interface HealthResponse {
  has_data: boolean;
  last_import_finished_at: string | null;
  vg250_source_version: string | null;
  region_join_match_rate: number | null;
  mastr_row_counts: Record<string, number> | null;
  capacity_rollup_row_count: number;
}

export interface UnitPoint {
  mastr_nummer: string;
  technology: string;
  category: string;
  capacity_kw: number | null;
  storage_capacity_kwh: number | null;
  latitude: number;
  longitude: number;
}

export interface UnitPointsResponse {
  points: UnitPoint[];
  truncated: boolean;
}
