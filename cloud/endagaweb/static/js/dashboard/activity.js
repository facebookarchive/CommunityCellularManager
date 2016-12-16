/*
 * Copyright (c) 2016-present, Facebook, Inc.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree. An additional grant
 * of patent rights can be found in the PATENTS file in the same directory.
 */

function setloading() {
    var $btn = $('#submit').button().button('loading');
}

$(function() {
  var options = {
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
    format: 'YYYY-MM-DD [at] hh:mmA',
  };
  $('#start_date').datetimepicker(options);
  $('#end_date').datetimepicker(options);
});
