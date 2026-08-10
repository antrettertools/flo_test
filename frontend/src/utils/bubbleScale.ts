interface BubbleRadiusOptions {
  maxCapacityKw: number;
  minRadius?: number;
  maxRadius?: number;
}

export function bubbleRadiusPx(capacityKw: number | null, opts: BubbleRadiusOptions): number {
  const { maxCapacityKw, minRadius = 3, maxRadius = 24 } = opts;
  if (capacityKw == null || capacityKw <= 0 || maxCapacityKw <= 0) return minRadius;
  const scale = Math.sqrt(capacityKw) / Math.sqrt(maxCapacityKw);
  return minRadius + scale * (maxRadius - minRadius);
}
