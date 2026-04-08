`default_nettype none

module ppu_lcd_off_quiescence_formal;
    localparam [2:0] PHASE_LCD_OFF = 3'd0;
    localparam [2:0] MODE_LCD_OFF = 3'd0;
    localparam [1:0] RUN_DISABLED = 2'd0;
    localparam [3:0] MMIO_LCDC = 4'd0;

    wire clk = $global_clock;

    reg [3:0] seq = 4'd0;
    reg f_past_valid = 1'b0;

    wire rst_i = seq == 4'd0;
    wire dot_ce_i = 1'b1;
    wire write_valid_i = seq == 4'd1;
    wire [3:0] write_target_i = MMIO_LCDC;
    wire [7:0] write_value_i = 8'h00;

    wire [40:0] surface;
    wire [2:0] phase = surface[2:0];
    wire [7:0] ly = surface[10:3];
    wire [8:0] dot = surface[19:11];
    wire [2:0] mode = surface[22:20];
    wire stat_line = surface[23];
    wire vblank_irq = surface[24];
    wire stat_irq = surface[25];
    wire [1:0] run = surface[27:26];
    wire first_frame_blank = surface[28];
    wire [7:0] stat_readback = surface[36:29];
    wire [2:0] mem_req_count = surface[39:37];
    wire scanout_valid = surface[40];

    \iceboy::ppu::rtl::core_test_top::core_test_top dut (
        .clk_i_i(clk),
        .rst_i_i(rst_i),
        .dot_ce_i_i(dot_ce_i),
        .write_valid_i_i(write_valid_i),
        .write_target_i_i(write_target_i),
        .write_value_i_i(write_value_i),
        .output__(surface)
    );

    always @(posedge clk) begin
        f_past_valid <= 1'b1;
        seq <= seq + 4'd1;
    end

    always @(posedge clk) begin
        if (f_past_valid && $past(seq) >= 4'd2) begin
            assert(mode == MODE_LCD_OFF);
            assert(phase == PHASE_LCD_OFF);
            assert(run == RUN_DISABLED);
            assert(ly == 8'd0);
            assert(dot == 9'd0);
            assert(mem_req_count == 3'd0);
            assert(!scanout_valid);
            assert(!stat_line);
            assert(!vblank_irq);
            assert(!stat_irq);
            assert(!first_frame_blank);
            assert(stat_readback[1:0] == 2'b00);
        end

        if (f_past_valid && $past(seq) >= 4'd3) begin
            assert(mode == $past(mode));
            assert(phase == $past(phase));
            assert(run == $past(run));
            assert(ly == $past(ly));
            assert(dot == $past(dot));
            assert(mem_req_count == $past(mem_req_count));
            assert(scanout_valid == $past(scanout_valid));
            assert(vblank_irq == $past(vblank_irq));
            assert(stat_irq == $past(stat_irq));
        end
    end
endmodule

`default_nettype wire
