odoo.define('js_addons.fixedTableHeaders', function (require) {
    "use strict";

    console.log('[js_addons] JS Addons Init...');

    var ListView = require('web.ListView');
    var fixedTablesActive = false;

    $.fn.hasScrollBar = function() {
        var hasScrollBar = this[0] ? this[0].scrollHeight > this.innerHeight() : false;
        //console.info('HAS SCROLLBAR', hasScrollBar);
        return hasScrollBar;
    }

    $.fn.scrollEnds = function() {
        var scrollEnds = (this.scrollTop() + this.innerHeight() >= this[0].scrollHeight);
        //console.info('[js_addons] SCROLL ENDS', scrollEnds);
        return scrollEnds;
    }

    $.isStandaloneListView = function() {
        var $container = $('div.o_view_manager_content:not(.o_form_field)');
        // Is standalone view if: (CONTAINER EXITS) AND (BUTTON ".o_cp_switch_list" EXISTS AND HAS CLASS "active") AND (CONTAINER CHILD NOT HAS CLASS "o_form_view")
        var isStandaloneListView = ($container.length === 1 && $('button.o_cp_switch_list.active').length === 1 && $container.children('div.o_form_view').length === 0);
        //console.info('[js_addons] IS STANDALONE LISTVIEW', isStandaloneListView);
        return isStandaloneListView;
    }

    $.scrollIndicator = function() {
        var $indicator = $('#fixed-table-scroll-indicator');
        if (!$indicator.length) $indicator = $('<div id="fixed-table-scroll-indicator" title="Hay más elementos ¡haz scroll!"><div></div></div>').appendTo($('div.o_view_manager_content:not(.o_form_field)')).hide();
        //console.info('[js_addons] SCROLL INDICATOR', $indicator);
        return $indicator;
    }

    $.fixTableButton = function() {
        var $container = $('div.o_cp_right');
        $container.find('div.btn-fxt-toggle').remove();
        var icon = (fixedTablesActive)? 'fa-toggle-on':'fa-toggle-off';
        var $newBtn = $('<div class="btn-group btn-group-sm o_cp_switch_buttons btn-fxt-toggle"/>');
        $('<button type="button" class="btn btn-icon fa fa-lg ' + icon + '" data-original-title="Cabecera"></button>').appendTo($newBtn).tooltip();
        //console.info('[js_addons] FIX BUTTON', $newBtn);
        return $newBtn.appendTo($('div.o_cp_right'));
    }

    $.setTableHeaderFixedIfActive = function() {
        // Tables to apply
        var $tableObj = $('div.o_view_manager_content:not(.o_form_field)').find('table');
        var $tableBody = $tableObj.find('tbody');

        //console.info('[js_addons] SET TABLE HEADER FIXED:', fixedTablesActive);

        if (fixedTablesActive){
            // Set button status
            $('div.btn-fxt-toggle button').removeClass('fa-toggle-off').addClass('fa-toggle-on');
            // Activate fixed header
            $tableObj.addClass('fixed-table-header');
            // If has scroll
            if ($tableBody.hasScrollBar()){
                $.scrollIndicator().fadeIn('slow');
                $tableBody.scroll(function() {
                    // If scroll reaches end
                    if ($tableBody.scrollEnds()) $.scrollIndicator().fadeOut('slow');
                });
            }
        }else{
            // Set button status
            $('div.btn-fxt-toggle button').removeClass('fa-toggle-on').addClass('fa-toggle-off');
            // Deactivate fixed header
            $tableObj.removeClass('fixed-table-header');
            $.scrollIndicator().fadeOut('fast');
        }
    }

    ListView.include({
        reload_content: function(){
            var reloaded = $.Deferred();

            // Set toggle btn on o_control_panel
            if ($.isStandaloneListView()){
                $.fixTableButton().click(function(){
                    fixedTablesActive = !fixedTablesActive;
                    $.setTableHeaderFixedIfActive();
                });
            }

            $('div.o_cp_switch_buttons, div.o_sub_menu_content, nav.oe_main_menu_navbar').off().click(function(){
                // Workaround to remove toggle button
                $.fixTableButton().remove();
            });

            this._super().then(function(){
                // console.log('[js_addons] View render...');
                // Set table fixed header if active
                $.setTableHeaderFixedIfActive();
                // Resolve the promise
                reloaded.resolve();
            }).then(function(){
                // Set toggle btn on o_control_panel
                if ($.isStandaloneListView()){
                    $.fixTableButton().click(function(){
                        fixedTablesActive = !fixedTablesActive;
                        $.setTableHeaderFixedIfActive();
                    });
                }else $.fixTableButton().remove();
            });

            return reloaded.promise();
        }
    });
});
