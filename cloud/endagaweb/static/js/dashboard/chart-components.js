/*
 * Copyright (c) 2016-present, Facebook, Inc.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree. An additional grant
 * of patent rights can be found in the PATENTS file in the same directory.
 */

// React chart components.


var TimeseriesChartWithButtonsAndDatePickers = React.createClass({

  getInitialState: function() {
    // We expect many of these values to be overridden before the chart is
    // first rendered -- see componentDidMount.
    return {
      startTimeEpoch: 0,
      endTimeEpoch: -1,
      isLoading: true,
      chartData: {},
      activeButtonText: '',
      xAxisFormatter: '%x',
      yAxisFormatter: '',
    }
  },

  getDefaultProps: function() {
    // Load the current time with the user's clock if nothing is specified.  We
    // also specify the user's computer's timezone offset and use that to
    // adjust the graph data.
    var currentTime = Math.round(new Date().getTime() / 1000);
    return {
      title: 'title (set me!)',
      chartID: 'one',
      buttons: ['hour', 'day', 'week', 'month', 'year'],
      defaultButtonText: 'week',
      endpoint: '/api/v1/stats/network',
      statTypes: 'sms',
      levelID: 0,
      aggregation: 'count',
      yAxisLabel: 'an axis label (set me!)',
      currentTimeEpoch: currentTime,
      timezoneOffset: 0,
      tooltipUnits: '',
    }
  },

  // On-mount, build the charts with the default data.
  // Note that we have to load the current time here.
  componentDidMount: function() {
    this.setState({
      activeButtonText: this.props.defaultButtonText,
      startTimeEpoch: this.props.currentTimeEpoch - secondsMap[this.props.defaultButtonText],
      endTimeEpoch: this.props.currentTimeEpoch,
    // When the request params in the state have been set, go get more data.
    }, function() {
      this.updateChartData();
    });
  },

  componentDidUpdate(prevProps, prevState) {
    // Update if we toggled a load
    if (!prevState.isLoading && this.state.isLoading) {
      this.updateChartData();
    }
  },

  // This handler takes the text of the date range buttons
  // and ouputs figures out the corresponding number of seconds.
  handleButtonClick: function(text) {
    // Update only if the startTime has actually changed.
    var newStartTimeEpoch = this.props.currentTimeEpoch - secondsMap[text];
    if (this.state.startTimeEpoch != newStartTimeEpoch) {
      this.setState({
        startTimeEpoch: newStartTimeEpoch,
        endTimeEpoch: this.props.currentTimeEpoch,
        isLoading: true,
        activeButtonText: text,
      });
    }
  },

  // Datepicker handlers, one each for changing the start and end times.
  startTimeChange: function(newTime) {
    if (newTime < this.state.endTimeEpoch && !this.state.isLoading) {
      this.setState({
        startTimeEpoch: newTime,
        isLoading: true,
      });
    }
  },
  endTimeChange: function(newTime) {
    var now = moment().unix();
    if (newTime > this.state.startTimeEpoch && newTime < now
        && !this.state.isLoading) {
      this.setState({
        endTimeEpoch: newTime,
        isLoading: true,
      });
    }
  },

  // Gets new chart data from the backend.
  // Recall that this must be called explicitly..it's a bit different
  // than the normal react component connectivity.
  // First figure out how to set the interval (or, more aptly, the bin width)
  // and the x-axis formatter (see the d3 wiki on time formatting).
  updateChartData: function() {
    var interval, newXAxisFormatter, newYAxisFormatter;
    var delta = this.state.endTimeEpoch - this.state.startTimeEpoch;
    if (delta <= 60) {
      interval = 'seconds';
      newXAxisFormatter = '%-H:%M:%S';
    } else if (delta <= (60 * 60)) {
      interval = 'minutes';
      newXAxisFormatter = '%-H:%M';
    } else if (delta <= (24 * 60 * 60)) {
      interval = 'hours';
      newXAxisFormatter = '%-H:%M';
    } else if (delta <= (7 * 24 * 60 * 60)) {
      interval = 'hours';
      newXAxisFormatter = '%b %d, %-H:%M';
    } else if (delta <= (30 * 24 * 60 * 60)) {
      interval = 'days';
      newXAxisFormatter = '%b %d';
    } else if (delta <= (365 * 24 * 60 * 60)) {
      interval = 'days';
      newXAxisFormatter = '%b %d';
    } else {
      interval = 'months';
      newXAxisFormatter = '%x';
    }
    if (this.props.statTypes == 'total_data,uploaded_data,downloaded_data') {
      newYAxisFormatter = '.1f';
    } else {
      newYAxisFormatter = '';
    }
    var queryParams = {
      'start-time-epoch': this.state.startTimeEpoch,
      'end-time-epoch': this.state.endTimeEpoch,
      'interval': interval,
      'stat-types': this.props.statTypes,
      'level-id': this.props.levelID,
      'aggregation': this.props.aggregation,
    };
    $.get(this.props.endpoint, queryParams, function(data) {
      this.setState({
        isLoading: false,
        chartData: data,
        xAxisFormatter: newXAxisFormatter,
        yAxisFormatter: newYAxisFormatter,
      });
    }.bind(this));
  },

  render: function() {
    var fromDatepickerID = 'from-datepicker-' + this.props.chartID;
    var toDatepickerID = 'to-datepicker-' + this.props.chartID;
    return (
      <div>
        <h4>{this.props.title}</h4>
        <span>past &nbsp;&nbsp;</span>
        {this.props.buttons.map(function(buttonText, index) {
          return (
            <RangeButton
              buttonText={buttonText}
              activeButtonText={this.state.activeButtonText}
              onButtonClick={this.handleButtonClick}
              key={index}
            />
          );
        }, this)}
        <span className='spacer'></span>
        <DatePicker
          label='from'
          pickerID={fromDatepickerID}
          epochTime={this.state.startTimeEpoch}
          onDatePickerChange={this.startTimeChange}
        />
        <DatePicker
          label='to'
          pickerID={toDatepickerID}
          epochTime={this.state.endTimeEpoch}
          onDatePickerChange={this.endTimeChange}
        />
        <LoadingText
          visible={this.state.isLoading}
        />
        <TimeseriesChart
          chartID={this.props.chartID}
          data={this.state.chartData}
          xAxisFormatter={this.state.xAxisFormatter}
          yAxisFormatter={this.state.yAxisFormatter}
          yAxisLabel={this.props.yAxisLabel}
          timezoneOffset={this.props.timezoneOffset}
          tooltipUnits={this.props.tooltipUnits}
        />
      </div>
    );
  },
});


var secondsMap = {
  'hour': 60 * 60,
  'day': 24 * 60 * 60,
  'week': 7 * 24 * 60 * 60,
  'month': 30 * 24 * 60 * 60,
  'year': 365 * 24 * 60 * 60,
};


// Builds the target chart from scratch.  NVD3 surprisingly handles this well.
// domTarget is the SVG element's parent and data is the info that will be graphed.
var updateChart = function(domTarget, data, xAxisFormatter, yAxisFormatter, yAxisLabel, timezoneOffset, tooltipUnits) {
  // We pass in the timezone offset and calculate a locale offset.  The former
  // is based on the UserProfile's specified timezone and the latter is the user's
  // computer's timezone offset.  We manually shift the data to work around
  // d3's conversion into the user's computer's timezone.  Note that for my laptop
  // in PST, the locale offset is positive (7hrs) while the UserProfile offset
  // is negative (-7hrs).
  var localeOffset = 60 * (new Date()).getTimezoneOffset();
  var shiftedData = [];
  for (var index in data) {
    var newSeries = { 'key': data[index]['key'] };
    var newValues = [];
    for (var series_index in data[index]['values']) {
      var newValue = [
        // Shift out of the locale offset to 'convert' to UTC and then shift
        // back into the operator's tz by adding the tz offset from the server.
        data[index]['values'][series_index][0] + 1e3 * localeOffset + 1e3 * timezoneOffset,
        data[index]['values'][series_index][1]
      ];
      newValues.push(newValue);
    }
    newSeries['values'] = newValues;
    shiftedData.push(newSeries);
  }

  nv.addGraph(function() {
    var chart = nv.models.lineChart()
      .x(function(d) { return d[0] })
      .y(function(d) { return d[1] })
      .color(d3.scale.category10().range())
      .interpolate('monotone')
      .showYAxis(true)
      ;
    chart.xAxis
      .tickFormat(function(d) {
        return d3.time.format(xAxisFormatter)(new Date(d));
      });
    // Fixes x-axis time alignment.
    chart.xScale(d3.time.scale.utc());
    chart.yAxis
      .axisLabel(yAxisLabel)
      .axisLabelDistance(25)
      .tickFormat(d3.format(yAxisFormatter));
    // Fixes the axis-labels being rendered out of the SVG element.
    chart.margin({right: 80});
    chart.tooltipContent(function(key, x, y) {
      return '<p>' + y + tooltipUnits + ' ' + key + '</p>' + '<p>' + x + '</p>';
    });
    // TODO(matt): non-negative y-axis
    d3.select(domTarget)
      .datum(shiftedData)
      .call(chart);
    // Resize the chart on window resize.
    nv.utils.windowResize(chart.update);
    return chart;
  });
};


var TimeseriesChart = React.createClass({

  getDefaultProps: function() {
    return {
      chartID: 'some-chart-id',
      chartHeight: 380,
      data: {},
      xAxisFormatter: '%x',
      yAxisFormatter: '',
      yAxisLabel: 'the y axis!',
      timezoneOffset: 0,
      tooltipUnits: '',
    }
  },

  chartIsFlat(results) {
    return results.every(function(series) {
      return series['values'].every(function(pair) {
        return pair[1] === 0;
      });
    });
  },

  render: function() {
    var results = this.props.data['results'];
    var isFlatChart = !results || this.chartIsFlat(results);
    var className = ['time-series-chart-container'];
    var flatLineOverlay = null;
    if (isFlatChart) {
      flatLineOverlay = (
        <div className='flat-chart-overlay'
             style={{height: this.props.chartHeight}}>
          <div style={{"line-height": this.props.chartHeight - 20}}>
            No data available for this range.
          </div>
        </div>
      );
      className.push('flat');
    }
    return (
      <div className={className.join(' ')}>
        {flatLineOverlay}
        <TimeSeriesChartElement {...this.props}/>
      </div>
    );
  }
});


var TimeSeriesChartElement = React.createClass({
  // When the request params have changed, get new data and rebuild the graph.
  // We circumvent react's typical re-render cycle for this component by returning false.
  shouldComponentUpdate: function(nextProps) {
    var nextData = JSON.stringify(nextProps.data);
    var prevData = JSON.stringify(this.props.data);
    if (nextData !== prevData) {
      updateChart(
        '#' + this.props.chartID,
        nextProps.data['results'],
        nextProps.xAxisFormatter,
        nextProps.yAxisFormatter,
        nextProps.yAxisLabel,
        this.props.timezoneOffset,
        this.props.tooltipUnits
      );
    }
    return false;
  },

  render: function() {
    var inlineStyles = {
      height: this.props.chartHeight
    };
    return (
      <svg id={this.props.chartID}
           className="time-series-chart"
           style={inlineStyles}>
      </svg>
    );
  }
});


var RangeButton = React.createClass({
  propTypes: {
    buttonText: React.PropTypes.string.isRequired
  },

  getDefaultProps: function() {
    return {
      buttonText: 'day',
      activeButtonText: '',
      onButtonClick: null,
    }
  },

  render: function() {
    // Determine whether this particular button is active by checking
    // this button's text vs the owner's knowledge of the active button.
    // Then change styles accordingly.
    var inlineStyles = {
      marginRight: 20
    };
    if (this.props.buttonText == this.props.activeButtonText) {
      inlineStyles.cursor = 'inherit';
      inlineStyles.color = 'black';
      inlineStyles.textDecoration = 'none';
    } else {
      inlineStyles.cursor = 'pointer';
    }
    return (
      <a style={inlineStyles} onClick={this.onThisClick.bind(this, this.props.buttonText)}>
        {this.props.buttonText}
      </a>
    );
  },

  onThisClick: function(text) {
    this.props.onButtonClick(text);
  },
});


var LoadingText = React.createClass({
  getDefaultProps: function() {
    return {
      visible: false,
    }
  },

  render: function() {
    var inlineStyles = {
      display: this.props.visible ? 'inline' : 'none',
      marginRight: 20,
    };

    return (
      <span className="loadingText" style={inlineStyles}>
        (loading..)
      </span>
    );
  },
});


var DatePicker = React.createClass({
  getDefaultProps: function() {
    return {
      label: 'date',
      pickerID: 'some-datetimepicker-id',
      epochTime: 0,
      onDatePickerChange: null,
      datePickerOptions : {
        icons: {
          time: 'fa fa-clock-o',
          date: 'fa fa-calendar',
          up: 'fa fa-arrow-up',
          down: 'fa fa-arrow-down',
          previous: 'fa fa-arrow-left',
          next: 'fa fa-arrow-right',
          today: 'fa fa-circle-o',
        },
        showTodayButton: true,
        format: 'YYYY-MM-DD [at] h:mmA',
      },
      dateFormat: 'YYYY-MM-DD [at] h:mmA',
    }
  },

  componentDidMount: function() {
    var formattedDate = moment.unix(this.props.epochTime).format(this.props.dateFormat);
    var domTarget = '#' + this.props.pickerID;
    $(domTarget)
      .datetimepicker(this.props.datePickerOptions)
      .data('DateTimePicker')
      .date(formattedDate);
    var dateFormat = this.props.dateFormat;
    var handler = this.props.onDatePickerChange;
    $(domTarget).on('dp.change', function(event) {
      var newEpochTime = moment(event.target.value, dateFormat).unix();
      handler(newEpochTime);
    });
  },

  shouldComponentUpdate: function(nextProps) {
    var formattedDate = moment.unix(nextProps.epochTime).format(nextProps.dateFormat);
    var domTarget = '#' + nextProps.pickerID;
    $(domTarget).data('DateTimePicker').date(formattedDate);
    return false
  },

  render: function() {
    return (
      <span className='datepicker'>
        <label>{this.props.label}</label>
        <input id={this.props.pickerID} type="text" />
      </span>
    );
  },
});
