`default_nettype none

module cpu_hold_formal;
    wire clk = $global_clock;

    reg rst = 1'b1;
    reg past_valid = 1'b0;
    reg check_hold = 1'b0;
    (* anyseq *) reg [7:0] bus_resp;
    (* anyseq *) reg [4:0] irq_pending;

    wire [99:0] hold_surface;

    \iceboy::cpu::formal_invariants_top::cpu_hold_top dut (
        .clk_i(clk),
        .rst_i(rst),
        .bus_resp_i(bus_resp),
        .irq_pending_i(irq_pending),
        .output__(hold_surface)
    );

    always @(posedge clk) begin
        past_valid <= 1'b1;
        if (rst) begin
            rst <= 1'b0;
        end else if (!check_hold) begin
            check_hold <= 1'b1;
        end else if (past_valid) begin
            assert(hold_surface == $past(hold_surface));
            assert(hold_surface[1:0] == 2'b00);
        end
    end
endmodule

`default_nettype wire
