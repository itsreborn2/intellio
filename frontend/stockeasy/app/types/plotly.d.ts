/**
 * react-plotly.js 모듈 타입 선언
 */
declare module 'react-plotly.js' {
  import * as Plotly from 'plotly.js';
  import * as React from 'react';

  interface PlotParams {
    data?: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    frames?: Plotly.Frame[];
    revision?: number;
    onInitialized?: (figure: Plotly.Figure, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: Plotly.Figure, graphDiv: HTMLElement) => void;
    onPurge?: (figure: Plotly.Figure, graphDiv: HTMLElement) => void;
    onError?: (err: Error) => void;
    onClick?: (event: Plotly.PlotMouseEvent) => void;
    onClickAnnotation?: (event: Plotly.ClickAnnotationEvent) => void;
    onHover?: (event: Plotly.PlotMouseEvent) => void;
    onUnhover?: (event: Plotly.PlotMouseEvent) => void;
    onSelected?: (event: Plotly.PlotSelectionEvent) => void;
    onDeselect?: () => void;
    onRestyle?: (data: Plotly.RestyleEvent) => void;
    onRelayout?: (layout: Plotly.RelayoutEvent) => void;
    onAnimated?: () => void;
    onRedraw?: () => void;
    onAutoSize?: () => void;
    className?: string;
    style?: React.CSSProperties;
    divId?: string;
  }

  class Plot extends React.Component<PlotParams> {}
  export default Plot;
}
