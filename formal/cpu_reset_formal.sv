`default_nettype none

module cpu_reset_formal;
    wire clk = $global_clock;

    reg rst = 1'b1;
    reg m_ce = 1'b0;
    reg check_reset_surface = 1'b0;

    wire reset_surface_ok;

    \iceboy::cpu::formal_invariants_top::cpu_reset_top dut (
        .clk_i(clk),
        .rst_i(rst),
        .m_ce_i(m_ce),
        .bus_resp_i(8'h00),
        .irq_pending_i(5'h00),
        .output__(reset_surface_ok)
    );

    always @(posedge clk) begin
        if (rst) begin
            rst <= 1'b0;
        end else if (!m_ce) begin
            m_ce <= 1'b1;
            check_reset_surface <= 1'b1;
        end else begin
            check_reset_surface <= 1'b0;
        end
    end

    always @(*) begin
        if (check_reset_surface) begin
            assert(reset_surface_ok);
        end
    end
endmodule

`default_nettype wire
