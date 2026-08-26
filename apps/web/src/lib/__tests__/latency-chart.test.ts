/** The planner-latency chart's scale and gaps.
 *
 * Both decisions are invisible in a screenshot: a sawtooth through
 * "the planner did not run" reads as varying latency, and an axis that
 * omits the budget reads as a shape with no verdict attached.
 */

import { describe, expect, it } from "vitest";

import {
  CHART,
  PLOT_WIDTH,
  latencyPlot,
  playheadFraction,
  timeAtFraction,
} from "@/lib/latencyChart";

const PERIOD = 0.05; // 50 ms, the deployment's control period

describe("ticks where the planner did not run", () => {
  it("breaks the line instead of drawing them as zero", () => {
    // A polyline through the zeros dives to the axis between replans and
    // draws a sawtooth that looks like wildly varying latency.
    const plot = latencyPlot([0, 0.1, 0.2, 0.3, 0.4], [4, 5, 0, 0, 6], PERIOD);
    expect(plot?.segments.map((segment) => segment.points.length)).toEqual([2, 1]);
  });

  it("does not let a gap raise or lower the peak", () => {
    const plot = latencyPlot([0, 0.1, 0.2], [4, 0, 6], PERIOD);
    expect(plot?.segments.flatMap((s) => s.points).every((point) => point.ms > 0)).toBe(true);
  });

  it("returns nothing when the planner never ran", () => {
    // An empty frame beats an axis with no line in it, which reads as a
    // chart that failed to load.
    expect(latencyPlot([0, 0.1], [0, 0], PERIOD)).toBeNull();
  });

  it("keeps a single unbroken run as one segment", () => {
    const plot = latencyPlot([0, 0.1, 0.2], [4, 5, 6], PERIOD);
    expect(plot?.segments).toHaveLength(1);
  });
});

describe("the vertical scale", () => {
  it("keeps the budget on the chart when the run is nowhere near it", () => {
    // Measured range on a healthy trace: 0.66–11.24 ms against 50 ms.
    // Scaling to the data alone would push the threshold off the top and
    // leave a shape with nothing to judge it against.
    const plot = latencyPlot([0, 0.1], [3.7, 11.2], PERIOD);
    expect(plot?.msMax).toBeGreaterThan(50);
    expect(plot?.breached).toBe(false);
  });

  it("scales to the spike when one blows through the budget", () => {
    // Candidate B on a timeout episode: p99 of 2101 ms.
    const plot = latencyPlot([0, 0.1], [4, 2101], PERIOD);
    expect(plot?.msMax).toBeGreaterThan(2101);
    expect(plot?.breached).toBe(true);
  });

  it("leaves headroom so a peak is not clipped into a plateau", () => {
    const plot = latencyPlot([0, 0.1], [4, 2101], PERIOD);
    expect(plot!.msMax).toBeGreaterThan(2101);
  });

  it("takes the threshold from the deployment, not from a constant", () => {
    // A deployment declaring a different control rate gets a different
    // line; a hard-coded 50 would quietly mis-grade it.
    expect(latencyPlot([0], [4], 0.1)?.budgetMs).toBe(100);
    expect(latencyPlot([0], [4], 0.02)?.budgetMs).toBe(20);
  });
});

describe("the playhead", () => {
  const plot = latencyPlot([0, 1, 2, 3, 4], [4, 4, 4, 4, 4], PERIOD)!;

  it("sits where the scrubber is", () => {
    expect(playheadFraction(plot, 2)).toBeCloseTo(0.5);
  });

  it("is absent past either end rather than pinned to the edge", () => {
    // Pinned, it would sit on the last sample and claim the replay is
    // there when it is not.
    expect(playheadFraction(plot, -1)).toBeNull();
    expect(playheadFraction(plot, 9)).toBeNull();
  });
});

describe("drawing only as far as the replay has got", () => {
  // 3 ms for a while, then a 900 ms spike at the very end.
  const times = [0, 1, 2, 3, 4];
  const latencies = [3, 3, 3, 3, 900];

  it("draws nothing past the playhead", () => {
    const plot = latencyPlot(times, latencies, PERIOD, 2);
    expect(plot!.segments[0].points.map((point) => point.t)).toEqual([0, 1, 2]);
  });

  it("does not let the scale give away a spike that has not happened", () => {
    // The whole point. An axis topping out at 900 ms announces the
    // blow-up several seconds before the line gets there, and the
    // reader watches a chart that has already told them the ending.
    const early = latencyPlot(times, latencies, PERIOD, 2)!;
    const late = latencyPlot(times, latencies, PERIOD, 4)!;
    expect(early.msMax).toBeLessThan(100);
    expect(late.msMax).toBeGreaterThan(900);
  });

  it("does not light the over-budget badge before the breach", () => {
    expect(latencyPlot(times, latencies, PERIOD, 3)!.breached).toBe(false);
    expect(latencyPlot(times, latencies, PERIOD, 4)!.breached).toBe(true);
  });

  it("keeps the time axis at the full episode from the first frame", () => {
    // A time axis that grew with the playhead would hold the line at
    // full width and squash its shape as it went, which reads as the
    // planner getting steadier when nothing changed.
    expect(latencyPlot(times, latencies, PERIOD, 0)!.tMax).toBe(4);
    expect(latencyPlot(times, latencies, PERIOD, 4)!.tMax).toBe(4);
  });

  it("never shrinks the vertical scale as the replay goes on", () => {
    // A scale free to shrink would redraw the whole line whenever a
    // peak stopped being the maximum of a moving window.
    const heights = times.map((_, index) => latencyPlot(times, latencies, PERIOD, index)!.msMax);
    expect(heights).toEqual([...heights].sort((left, right) => left - right));
  });

  it("clamps a playhead past either end rather than drawing nothing", () => {
    expect(latencyPlot(times, latencies, PERIOD, -3)!.segments[0].points).toHaveLength(1);
    expect(latencyPlot(times, latencies, PERIOD, 99)!.segments[0].points).toHaveLength(5);
  });

  it("still draws the whole episode when no playhead is given", () => {
    expect(latencyPlot(times, latencies, PERIOD)!.segments[0].points).toHaveLength(5);
  });
});

describe("clicking the chart to seek", () => {
  const plot = latencyPlot([0, 5, 10], [4, 4, 4], PERIOD)!;

  it("maps the middle of the plotting area to the middle of the episode", () => {
    // The padding is part of the element, so the middle of the *element*
    // is not the middle of the *plot*. Getting this wrong would seek a
    // couple of seconds off on a short episode and still look right,
    // because the playhead is drawn with the same offset.
    const middleOfPlot = (CHART.padLeft + PLOT_WIDTH / 2) / CHART.width;
    expect(timeAtFraction(plot, middleOfPlot)).toBeCloseTo(5);
  });

  it("puts the two ends of the plot at the two ends of the episode", () => {
    expect(timeAtFraction(plot, CHART.padLeft / CHART.width)).toBeCloseTo(0);
    expect(timeAtFraction(plot, (CHART.padLeft + PLOT_WIDTH) / CHART.width)).toBeCloseTo(10);
  });

  it("clamps a click on the axis labels rather than seeking outside the run", () => {
    // The left gutter holds the scale labels and is part of the click
    // target; a click there should mean "the start", not a negative time
    // the scrubber would refuse.
    expect(timeAtFraction(plot, 0)).toBe(0);
    expect(timeAtFraction(plot, 1)).toBeCloseTo(10);
  });
});
