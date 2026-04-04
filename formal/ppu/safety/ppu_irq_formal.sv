`default_nettype none

module ppu_irq_formal;
    wire clk = $global_clock;

    reg rst = 1'b1;

    (* anyseq *) reg [1:0] prev_run_i;
    (* anyseq *) reg [2:0] prev_phase_i;
    (* anyseq *) reg [1:0] next_run_i;
    (* anyseq *) reg [2:0] next_phase_i;
    (* anyseq *) reg [7:0] line_i;
    (* anyseq *) reg [7:0] ly_i;
    (* anyseq *) reg [7:0] lyc_i;
    (* anyseq *) reg prev_line_high_i;
    (* anyseq *) reg lyc_sel_i;
    (* anyseq *) reg mode2_sel_i;
    (* anyseq *) reg mode1_sel_i;
    (* anyseq *) reg mode0_sel_i;
    (* anyseq *) reg stat_write_seen_i;
    (* anyseq *) reg quirk_enable_i;

    wire [9:0] irq_surface;
    wire lyc_match = irq_surface[0];
    wire new_line = irq_surface[1];
    wire next_line_high = irq_surface[2];
    wire entered_vblank = irq_surface[3];
    wire quirk_pulse = irq_surface[4];
    wire edge_req = irq_surface[5];
    wire vblank_req = irq_surface[6];
    wire stat_req = irq_surface[7];
    wire next_run_active = next_run_i == 2'd1 || next_run_i == 2'd2;

    \iceboy::ppu::rtl::irq_test_top::irq_test_top dut (
        .prev_run_i_i(prev_run_i),
        .prev_phase_i_i(prev_phase_i),
        .next_run_i_i(next_run_i),
        .next_phase_i_i(next_phase_i),
        .line_i_i(line_i),
        .ly_i_i(ly_i),
        .lyc_i_i(lyc_i),
        .prev_line_high_i_i(prev_line_high_i),
        .lyc_sel_i_i(lyc_sel_i),
        .mode2_sel_i_i(mode2_sel_i),
        .mode1_sel_i_i(mode1_sel_i),
        .mode0_sel_i_i(mode0_sel_i),
        .stat_write_seen_i_i(stat_write_seen_i),
        .quirk_enable_i_i(quirk_enable_i),
        .output__(irq_surface)
    );

    always @(posedge clk) begin
        rst <= 1'b0;
    end

    always @(*) begin
        if (!rst && next_run_i == 2'd0) begin
            assert(!new_line);
            assert(!next_line_high);
            assert(!vblank_req);
        end

        if (!rst && next_run_i == 2'd0 && !(quirk_enable_i && stat_write_seen_i)) begin
            assert(!edge_req);
            assert(!stat_req);
        end

        if (!rst && prev_line_high_i && new_line && !(quirk_enable_i && stat_write_seen_i)) begin
            assert(!edge_req);
            assert(!stat_req);
        end

        if (!rst && !lyc_sel_i && !mode2_sel_i && !mode1_sel_i && !mode0_sel_i && !stat_write_seen_i) begin
            assert(!new_line);
            assert(!next_line_high);
            assert(!edge_req);
            assert(!stat_req);
        end

        if (!rst && quirk_pulse) begin
            assert(quirk_enable_i);
            assert(stat_write_seen_i);
            assert(stat_req);
        end

        if (!rst && vblank_req) begin
            assert(entered_vblank);
        end

        if (!rst && entered_vblank) begin
            assert(vblank_req);
        end

        if (!rst && lyc_sel_i && ly_i == lyc_i && next_run_active && next_phase_i == 3'd3) begin
            assert(lyc_match);
            assert(new_line);
        end
    end
endmodule

`default_nettype wire
