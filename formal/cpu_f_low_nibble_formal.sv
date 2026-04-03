`default_nettype none

module cpu_f_low_nibble_formal;
    wire clk = $global_clock;

    reg rst = 1'b1;
    always @(posedge clk) begin
        rst <= 1'b0;
    end

    (* anyseq *) reg m_ce;
    (* anyseq *) reg [7:0] bus_resp;
    (* anyseq *) reg [4:0] irq_pending;

    wire f_low_nibble_zero;

    \iceboy::cpu::formal_invariants_top::cpu_f_low_nibble_top dut (
        .clk_i(clk),
        .rst_i(rst),
        .m_ce_i(m_ce),
        .bus_resp_i(bus_resp),
        .irq_pending_i(irq_pending),
        .output__(f_low_nibble_zero)
    );

    reg started = 1'b0;
    always @(posedge clk) begin
        started <= 1'b1;
    end

    always @(*) begin
        if (started) begin
            assert(f_low_nibble_zero);
        end
    end
endmodule

`default_nettype wire
