`default_nettype none

module ppu_timing_formal;
    localparam [2:0] PHASE_LCD_OFF = 3'd0;
    localparam [2:0] PHASE_OAM = 3'd1;
    localparam [2:0] PHASE_TRANSFER = 3'd2;
    localparam [2:0] PHASE_HBLANK = 3'd3;
    localparam [2:0] PHASE_VBLANK = 3'd4;

    localparam [2:0] MODE_OAM = 3'd2;
    localparam [2:0] MODE_LCD_OFF = 3'd4;

    wire clk = $global_clock;

    reg rst = 1'b1;

    (* anyseq *) reg [1:0] run_i;
    (* anyseq *) reg [2:0] phase_i;
    (* anyseq *) reg [7:0] ly_i;
    (* anyseq *) reg [8:0] dot_in_line_i;
    (* anyseq *) reg [8:0] dots_left_i;
    (* anyseq *) reg [2:0] sampled_scx_low3_i;
    (* anyseq *) reg sampled_wy_triggered_i;
    (* anyseq *) reg sampled_window_enable_i;
    (* anyseq *) reg [7:0] scx_i;
    (* anyseq *) reg [7:0] wy_i;
    (* anyseq *) reg win_enable_i;
    (* anyseq *) reg old_lcdc_enable_i;
    (* anyseq *) reg new_lcdc_enable_i;

    wire [33:0] timing_surface;
    wire [2:0] next_phase = timing_surface[2:0];
    wire [7:0] next_ly = timing_surface[10:3];
    wire line_start = timing_surface[16];
    wire frame_start = timing_surface[17];
    wire [1:0] next_run = timing_surface[19:18];
    wire [2:0] visible_mode = timing_surface[22:20];
    wire lcd_enabled = timing_surface[23];
    wire [7:0] transitioned_ly = timing_surface[31:24];
    wire [1:0] transitioned_run = timing_surface[33:32];
    wire run_active = run_i == 2'd1 || run_i == 2'd2;

    \iceboy::ppu::rtl::timing_test_top::timing_test_top dut (
        .run_i_i(run_i),
        .phase_i_i(phase_i),
        .ly_i_i(ly_i),
        .dot_in_line_i_i(dot_in_line_i),
        .line_i_i(ly_i),
        .dots_left_i_i(dots_left_i),
        .sampled_scx_low3_i_i(sampled_scx_low3_i),
        .sampled_wy_triggered_i_i(sampled_wy_triggered_i),
        .sampled_window_enable_i_i(sampled_window_enable_i),
        .scx_i_i(scx_i),
        .wy_i_i(wy_i),
        .win_enable_i_i(win_enable_i),
        .old_lcdc_enable_i_i(old_lcdc_enable_i),
        .new_lcdc_enable_i_i(new_lcdc_enable_i),
        .output__(timing_surface)
    );

    always @(posedge clk) begin
        rst <= 1'b0;
    end

    always @(*) begin
        if (!rst && run_i == 2'd0) begin
            assert(next_phase == PHASE_LCD_OFF);
            assert(next_ly == 8'd0);
            assert(next_run == 2'd0);
        end

        if (!rst && !new_lcdc_enable_i) begin
            assert(visible_mode == MODE_LCD_OFF);
            assert(!lcd_enabled);
            assert(transitioned_ly == 8'd0);
            assert(transitioned_run == 2'd0);
        end

        if (!rst && !old_lcdc_enable_i && new_lcdc_enable_i) begin
            assert(visible_mode == MODE_OAM);
            assert(lcd_enabled);
            assert(transitioned_ly == 8'd0);
            assert(transitioned_run == 2'd1);
        end

        if (!rst && run_active && phase_i == PHASE_OAM && dot_in_line_i == 9'd79) begin
            assert(next_phase == PHASE_TRANSFER);
            assert(next_ly == ly_i);
        end

        if (!rst && run_active && phase_i == PHASE_TRANSFER && dot_in_line_i == 9'd251) begin
            assert(next_phase == PHASE_HBLANK);
            assert(next_ly == ly_i);
        end

        if (!rst && run_active && phase_i == PHASE_HBLANK && dot_in_line_i == 9'd455 && ly_i < 8'd143) begin
            assert(next_phase == PHASE_OAM);
            assert(next_ly == ly_i + 8'd1);
            assert(line_start);
            assert(!frame_start);
        end

        if (!rst && run_active && phase_i == PHASE_HBLANK && dot_in_line_i == 9'd455 && ly_i == 8'd143) begin
            assert(next_phase == PHASE_VBLANK);
            assert(next_ly == 8'd144);
            assert(line_start);
        end

        if (!rst && run_active && phase_i == PHASE_VBLANK && ly_i >= 8'd144) begin
            assert(next_ly >= 8'd144 || next_ly == 8'd0);
        end

        if (!rst && run_active && phase_i == PHASE_VBLANK && dot_in_line_i == 9'd455 && ly_i == 8'd153) begin
            assert(next_phase == PHASE_OAM);
            assert(next_ly == 8'd0);
            assert(line_start);
            assert(frame_start);
        end

        if (!rst && run_active && dot_in_line_i != 9'd455 && phase_i != PHASE_LCD_OFF) begin
            assert(next_ly == ly_i);
        end
    end
endmodule

`default_nettype wire
